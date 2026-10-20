"""Actual HTTP quote → order boundary; only external transports are doubled."""

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.modules.delivery.provider import CdekProviderError, CdekTariffQuote
from app.modules.delivery.quote_router import router as quote_router
from app.modules.delivery.quote_service import CdekQuoteService
from app.modules.orders.models import Order
from app.modules.orders.security import generate_order_guest_access_token
from tests.contract.test_checkout_api import CheckoutProvider, _application, _command, _headers


class ShippingProvider:
    def __init__(self):
        self.bodies = []
        self.error = None

    async def calculate_tariff(self, body):
        self.bodies.append(body)
        if self.error:
            raise self.error
        return CdekTariffQuote(delivery_sum=Decimal("50.00"), period_min=2, period_max=4)


def setup_quote_application(tmp_path):
    payments = CheckoutProvider()
    app, database, product_id, _ = _application(tmp_path, payments)
    shipping = ShippingProvider()
    # Register the real quote router/service while keeping external directory
    # refresh disabled: the test seeds the actual persistent directory itself.
    app.include_router(quote_router)
    app.state.cdek_quote_service = CdekQuoteService(
        app.state.settings.model_copy(update={"cdek_quote_enabled": True}), shipping
    )
    return app, database, product_id, shipping, payments


def quote_request(product_id, *, method="cdek_pickup", address="Forged address"):
    return {
        "city": "Moscow" if method == "cdek_door" else "Forged city",
        "delivery_method": method,
        "delivery_address": address,
        "cdek_point_code": "MSK1" if method == "cdek_pickup" else None,
        "cart_items": [{"product_id": product_id, "quantity": 2}],
    }


def test_http_quote_sets_canonical_destination_and_persisted_retry_survives_expiry(
    tmp_path, monkeypatch
):
    app, database, product_id, shipping, payments = setup_quote_application(tmp_path)
    headers = _headers(guest_token=generate_order_guest_access_token())
    with TestClient(app) as client:
        response = client.post("/api/cdek/calculate", json=quote_request(product_id))
        assert response.status_code == 200
        quote = response.json()
        assert quote["delivery_city"] == "Moscow"
        assert quote["delivery_address"] == "Moscow pickup point"
        assert quote["cdek_point_code"] == "MSK1"
        assert quote["delivery_price"] == 50
        assert response.headers["cache-control"] == "no-store"
        assert json.loads(shipping.bodies[0])["to_location"]["city"] == "Moscow"
        command = _command(
            product_id,
            quote=quote["quote_token"],
            delivery_price="0.00",
            delivery_city="Forged city",
            delivery_address="Forged address",
        )
        created = client.post("/api/orders", json=command, headers=headers)
        assert created.status_code == 200
        assert len(payments.calls) == 1

        from app.modules.delivery import quote_proof

        future = datetime.now(timezone.utc) + timedelta(minutes=16)

        class FutureClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return future if tz else future.replace(tzinfo=None)

        monkeypatch.setattr(quote_proof, "datetime", FutureClock)
        replayed = client.post("/api/orders", json=command, headers=headers)
        assert replayed.status_code == 200
        assert replayed.json() == created.json()
        expired_new = client.post(
            "/api/orders",
            json=command,
            headers={
                **headers,
                "Idempotency-Key": "new_checkout_after_quote_expiry",
            },
        )
        assert expired_new.status_code == 422
        with sqlite3.connect(tmp_path / "target.db") as connection:
            connection.execute("UPDATE delivery_directory_state SET updated_at=NULL")
        replay_during_outage = client.post("/api/orders", json=command, headers=headers)
        assert replay_during_outage.status_code == 200
        assert replay_during_outage.json() == created.json()

    async def verify():
        await database.startup()
        try:
            async with database.session() as session:
                assert await session.scalar(select(func.count()).select_from(Order)) == 1
                order = await session.get(Order, created.json()["order_id"])
                assert order.delivery_city == "Moscow"
                assert order.delivery_address == "Moscow pickup point"
                assert order.delivery_price == Decimal("50.00")
                assert order.total_price == Decimal("250.50")
        finally:
            await database.shutdown()

    asyncio.run(verify())
    assert len(payments.calls) == len(shipping.bodies) == 1


@pytest.mark.parametrize(
    "change",
    ["quantity", "signature", "logistics", "courier_address", "city_controls", "address_controls"],
)
def test_new_order_rejects_quote_reused_for_changed_shipping(tmp_path, change):
    app, _, product_id, shipping, payments = setup_quote_application(tmp_path)
    method = "cdek_door" if change in {"courier_address", "address_controls"} else "cdek_pickup"
    with TestClient(app) as client:
        issued = client.post(
            "/api/cdek/calculate",
            json=quote_request(
                product_id,
                method=method,
                address="Moscow, Street1",
            ),
        )
        assert issued.status_code == 200
        quote = issued.json()
        command = _command(
            product_id,
            quote=quote["quote_token"],
            delivery_method=method,
            delivery_city=quote["delivery_city"],
            delivery_address=quote["delivery_address"],
            cdek_point_code=quote["cdek_point_code"],
        )
        if change == "quantity":
            command["items"][0]["quantity"] = 3
            command["claimed_total_price"] = "350.75"
        elif change == "signature":
            head, body, signature = command["delivery_quote_token"].split(".")
            forged_body = json.loads(jwt.utils.base64url_decode(body))
            forged_body["amount"] = "0.00"
            forged_body = jwt.utils.base64url_encode(json.dumps(forged_body).encode()).decode()
            command["delivery_quote_token"] = ".".join([head, forged_body, signature])
            command["delivery_price"] = "0.00"
            command["claimed_total_price"] = "200.50"
        elif change == "logistics":
            with sqlite3.connect(tmp_path / "target.db") as connection:
                connection.execute("UPDATE products SET weight_kg=1")
        elif change == "city_controls":
            command["delivery_city"] = "Moscow\nDistrict"
        elif change == "address_controls":
            command["delivery_address"] = "Moscow\nOther Street99"
        else:
            command["delivery_address"] = "Moscow, Other Street99"
        response = client.post(
            "/api/orders",
            json=command,
            headers=_headers(guest_token=generate_order_guest_access_token()),
        )
        assert response.status_code == 422
        assert response.headers["cache-control"] == "no-store"
    assert payments.calls == []
    assert len(shipping.bodies) == 1
    with sqlite3.connect(tmp_path / "target.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM inventory_reservations").fetchone()[0] == 0


def test_quote_outage_has_no_free_delivery_fallback(tmp_path):
    app, _, product_id, shipping, payments = setup_quote_application(tmp_path)
    shipping.error = CdekProviderError("quote_failure", retryable=True)
    with TestClient(app) as client:
        failed = client.post("/api/cdek/calculate", json=quote_request(product_id))
        assert failed.status_code == 503
        assert "delivery_price" not in failed.json()
        assert "quote_token" not in failed.json()
        with sqlite3.connect(tmp_path / "target.db") as connection:
            connection.execute("UPDATE delivery_directory_state SET updated_at=NULL")
        unavailable = client.post("/api/cdek/calculate", json=quote_request(product_id))
        assert unavailable.status_code == 503
    assert len(shipping.bodies) == 1
    assert payments.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "DELETE FROM delivery_pickup_points",
        "UPDATE products SET weight_kg=0",
        "UPDATE products SET is_active=0",
    ],
)
def test_changed_delivery_inputs_return_a_terminal_checkout_code_without_an_order(
    tmp_path, mutation
):
    app, _, product_id, shipping, payments = setup_quote_application(tmp_path)
    with TestClient(app) as client:
        issued = client.post("/api/cdek/calculate", json=quote_request(product_id))
        assert issued.status_code == 200
        with sqlite3.connect(tmp_path / "target.db") as connection:
            connection.execute(mutation)
        rejected = client.post(
            "/api/orders",
            json=_command(product_id, quote=issued.json()["quote_token"]),
            headers=_headers(guest_token=generate_order_guest_access_token()),
        )
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == {"code": "checkout_delivery_unavailable"}
    assert payments.calls == []
    assert len(shipping.bodies) == 1
    with sqlite3.connect(tmp_path / "target.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM inventory_reservations").fetchone()[0] == 0
