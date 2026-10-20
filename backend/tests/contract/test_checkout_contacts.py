"""Buyer and recipient snapshots survive restart without sharing ownership."""

import asyncio
import json
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.delivery.canonical import CdekCanonicalRequestBuilder
from app.modules.delivery.quote_router import router as quote_router
from app.modules.fulfillment.handlers import OrderPaymentEmailHandler
from app.modules.fulfillment.models import FulfillmentJob
from app.modules.notifications.factory import build_notification_outbox_service
from app.modules.orders.repository import OrderRepository
from app.modules.orders.security import generate_order_guest_access_token
from app.modules.payments.models import Payment, PaymentAttempt
from app.modules.production.admin_reads import ProductionAdminReads, order_row
from tests.contract.test_checkout_api import (
    CheckoutProvider,
    _application,
    _command,
    _headers,
    _latest_otp,
)

BUYER = {"name": "Анна Покупатель", "phone": "+79991112233", "email": "buyer@example.test"}
RECIPIENT = {"name": "Иван Получатель", "phone": "+79994445566", "email": "recipient@example.test"}


def contacts_command(product_id, quote):
    command = _command(product_id, quote=quote)
    return {**command, "buyer": dict(BUYER), "recipient": dict(RECIPIENT)}


def sign_in(client, database_path, email):
    assert client.post("/api/auth/email/request", json={"email": email}).status_code == 200
    verified = client.post(
        "/api/auth/email/verify", json={"email": email, "code": _latest_otp(database_path)}
    )
    assert verified.status_code == 200
    return {"Authorization": "Bearer " + verified.json()["token"]}


@pytest.mark.parametrize("authenticated", [False, True])
def test_distinct_contacts_persist_and_recipient_cannot_read_order(tmp_path, authenticated):
    provider = CheckoutProvider()
    app, database, product_id, quote = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()
    headers = _headers(guest_token=None if authenticated else guest_token)
    with TestClient(app) as client:
        owner = sign_in(client, tmp_path / "target.db", BUYER["email"]) if authenticated else {}
        created = client.post(
            "/api/orders", json=contacts_command(product_id, quote), headers={**headers, **owner}
        )
        assert created.status_code == 200
        order_id = created.json()["order_id"]
    # A new lifespan/session reads the persistent snapshots, not request state.
    with TestClient(app) as client:
        if authenticated:
            read = client.get(f"/api/orders/{order_id}", headers=owner)
        else:
            read = client.get("/api/order-access", headers={"X-Order-Access-Token": guest_token})
        assert read.status_code == 200
        assert read.json()["buyer"] == BUYER
        assert read.json()["recipient"] == RECIPIENT
        stranger = sign_in(client, tmp_path / "target.db", RECIPIENT["email"])
        assert client.get(f"/api/orders/{order_id}", headers=stranger).status_code == 404
        assert client.get("/api/auth/orders", headers=stranger).json() == {
            "items": [],
            "next_cursor": None,
        }
        assert client.get("/api/order-access", headers=stranger).status_code == 404
        if not authenticated:
            buyer_session = sign_in(client, tmp_path / "target.db", BUYER["email"])
            assert client.get(f"/api/orders/{order_id}", headers=buyer_session).status_code == 404
            assert client.get("/api/auth/orders", headers=buyer_session).json() == {
                "items": [],
                "next_cursor": None,
            }

    receipt = json.loads(provider.calls[0][1])["receipt"]["customer"]
    assert receipt["email"] == BUYER["email"]

    async def persisted_shipping():
        await database.startup()
        try:
            async with database.session() as session:
                order = await OrderRepository().get_order(session, order_id)
                assert order.buyer_name == BUYER["name"]
                assert order.buyer_phone == BUYER["phone"]
                assert order.email_normalized == BUYER["email"]
                assert order.phone == RECIPIENT["phone"]
                assert order.recipient_email == RECIPIENT["email"]
                request = (
                    CdekCanonicalRequestBuilder(
                        database.settings.model_copy(update={"cdek_sender_name": "GARMENT BURO"})
                    )
                    .build(order)
                    .as_dict()
                )
                assert request["recipient"] == {
                    "name": RECIPIENT["name"],
                    "email": RECIPIENT["email"],
                    "phones": [{"number": RECIPIENT["phone"]}],
                }
        finally:
            await database.shutdown()

    asyncio.run(persisted_shipping())
    with sqlite3.connect(tmp_path / "target.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM refresh_sessions").fetchone()[0] == 2


@pytest.mark.parametrize("contact", ["buyer", "recipient"])
@pytest.mark.parametrize(
    "field,value", [("email", "not-an-email"), ("phone", "123"), ("name", " ")]
)
def test_invalid_contact_creates_no_order_or_payment(tmp_path, contact, field, value):
    provider = CheckoutProvider()
    app, _, product_id, quote = _application(tmp_path, provider)
    command = contacts_command(product_id, quote)
    command[contact][field] = value
    with TestClient(app) as client:
        response = client.post(
            "/api/orders",
            json=command,
            headers=_headers(guest_token=generate_order_guest_access_token()),
        )
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    if value.strip():
        assert value not in response.text
    assert provider.calls == []
    with sqlite3.connect(tmp_path / "target.db") as connection:
        for table in ("orders", "inventory_reservations", "payment_attempts", "refresh_sessions"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_paid_email_and_admin_contact_address_the_buyer(tmp_path):
    provider = CheckoutProvider(outcomes=["succeeded"])
    app, database, product_id, quote = _application(tmp_path, provider)
    with TestClient(app) as client:
        created = client.post(
            "/api/orders",
            json=contacts_command(product_id, quote),
            headers=_headers(guest_token=generate_order_guest_access_token()),
        )
        assert created.status_code == 200

    async def verify():
        await database.startup()
        try:
            async with database.session() as session:
                order_id = created.json()["order_id"]
                attempt = await session.scalar(
                    select(PaymentAttempt)
                    .join(Payment, Payment.id == PaymentAttempt.payment_id)
                    .where(Payment.order_id == order_id)
                )
                job = FulfillmentJob(
                    kind="customer_payment_email",
                    order_id=order_id,
                    source_payment_attempt_id=attempt.id,
                )
                handler = OrderPaymentEmailHandler(
                    build_notification_outbox_service(database.settings)
                )
                prepared = await handler.prepare(session, job, now=datetime.now(timezone.utc))
                assert prepared.recipient == BUYER["email"]
                assert prepared.first_name == BUYER["name"]
                order = await OrderRepository().get_order(session, order_id)
                admin = order_row((order, None))
                assert admin["name"] == BUYER["name"]
                assert admin["phone"] == BUYER["phone"]
                assert admin["email"] == BUYER["email"]
                reads = ProductionAdminReads()
                clients = await reads.clients(session, q=BUYER["phone"], limit=10, offset=0)
                assert len(clients["items"]) == 1
                assert clients["items"][0]["name"] == BUYER["name"]
                assert clients["items"][0]["phone"] == BUYER["phone"]
                from app.modules.production.client_service import ProductionClientService

                detail = await ProductionClientService().detail(
                    session, key=clients["items"][0]["key"]
                )
                assert detail["name"] == BUYER["name"]
                assert detail["phone"] == BUYER["phone"]
                assert detail["recipient"]["name"] == RECIPIENT["name"]
                assert detail["recipient"]["phone"] == RECIPIENT["phone"]
                assert detail["recipient"]["email"] == RECIPIENT["email"]
        finally:
            await database.shutdown()

    asyncio.run(verify())


@pytest.mark.parametrize("path", ["/api/orders", "/api/cdek/calculate"])
def test_public_purchase_schema_references_resolve_in_openapi_document(tmp_path, path):
    app, _, _, _ = _application(tmp_path, CheckoutProvider())
    app.include_router(quote_router)
    document = app.openapi()
    schema = document["paths"][path]["post"]["requestBody"]["content"]["application/json"]["schema"]

    def resolve(value):
        if isinstance(value, dict):
            if "$ref" in value:
                reference = value["$ref"]
                assert reference.startswith("#/")
                target = document
                for token in reference[2:].split("/"):
                    token = token.replace("~1", "/").replace("~0", "~")
                    assert token in target, f"Unresolved OpenAPI reference: {reference}"
                    target = target[token]
                resolve(target)
            for key, child in value.items():
                if key != "$ref":
                    resolve(child)
        elif isinstance(value, list):
            for child in value:
                resolve(child)

    resolve(schema)
