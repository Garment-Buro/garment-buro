from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import count
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.factory import create_app
from app.integrations.minio import MinioStorage
from app.modules.catalog.models import CatalogMigrationRun, Product, ProductVariant
from app.modules.checkout.service import CheckoutService
from app.modules.identity.models import IdentityMigrationRun
from app.modules.identity.repository import IdentityRepository
from app.modules.inventory.models import InventoryReservation
from app.modules.notifications.crypto import (
    EncryptedNotificationPayload,
    NotificationPayloadCodec,
)
from app.modules.orders.models import Order, OrderCreationRequest, OrderMigrationRun
from app.modules.orders.security import generate_order_guest_access_token
from app.modules.payments.creation import PaymentCreationService
from app.modules.payments.models import PaymentAttempt
from app.modules.payments.provider import AiohttpYooKassaTransport, YooKassaProviderError
from app.modules.payments.schemas import ProviderPaymentSnapshot
from app.modules.payments.service import PaymentService
from tests.fakes.minio import FakeMinioClient

CATALOG_FINGERPRINT = "a" * 64
IDENTITY_FINGERPRINT = "b" * 64
ORDER_FINGERPRINT = "c" * 64
JWT_SECRET = "j" * 32
OTP_PEPPER = "p" * 32
NOTIFICATION_KEY = base64.urlsafe_b64encode(b"n" * 32).decode("ascii").rstrip("=")
PROVIDER_PAYMENT_ID = "2c111111-000f-5000-a000-111111111111"


def _settings(path: Path, *, checkout_enabled: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        public_base_url="https://shop.example.test",
        legacy_database_url="sqlite:///missing-legacy.db",
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.example.test",
        catalog_reads_enabled=True,
        catalog_migration_fingerprint=CATALOG_FINGERPRINT,
        identity_api_enabled=True,
        identity_migration_fingerprint=IDENTITY_FINGERPRINT,
        jwt_secret=JWT_SECRET,
        identity_otp_pepper=OTP_PEPPER,
        notification_encryption_key=NOTIFICATION_KEY,
        order_reads_enabled=True,
        order_migration_fingerprint=ORDER_FINGERPRINT,
        yookassa_shop_id="shop-id",
        yookassa_api_key="payment-secret",
        payment_creation_enabled=True,
        yookassa_receipt_tax_system_code=1,
        yookassa_receipt_product_vat_code=1,
        yookassa_receipt_delivery_vat_code=1,
        yookassa_receipt_product_payment_mode="full_payment",
        yookassa_receipt_delivery_payment_mode="full_payment",
        yookassa_receipt_product_subject="non_marked",
        yookassa_receipt_delivery_subject="service",
        checkout_v2_enabled=checkout_enabled,
    )


def _command(product_id: int, **updates: object) -> dict[str, object]:
    command: dict[str, object] = {
        "email": "customer@example.test",
        "phone": "+7 900 000-00-00",
        "first_name": "Customer",
        "delivery_city": "Moscow",
        "delivery_method": "cdek_pickup",
        "delivery_address": "Moscow pickup point",
        "cdek_point_code": "MSK1",
        "payment_method": "card",
        "items": [
            {
                "id": "checkout-line-1",
                "product_id": product_id,
                "title": "Untrusted client title",
                "price": "1.00",
                "image": "/uploads/item.webp",
                "size": "M",
                "color": "black",
                "quantity": 2,
            }
        ],
        "claimed_total_price": "250.50",
        "delivery_price": "50.00",
        "currency": "RUB",
    }
    command.update(updates)
    return command


@dataclass
class CheckoutProvider:
    outcomes: list[str] = field(default_factory=lambda: ["success"])
    calls: list[tuple[str, bytes]] = field(default_factory=list)

    async def create_payment(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> ProviderPaymentSnapshot:
        self.calls.append((idempotence_key, request_body))
        outcome = self.outcomes.pop(0)
        if outcome == "timeout":
            raise YooKassaProviderError(
                "timeout",
                retryable=True,
                outcome_unknown=True,
            )
        if outcome == "rejected":
            raise YooKassaProviderError(
                "request_rejected",
                retryable=False,
                rejected=True,
            )
        payload = json.loads(request_body)
        status = "canceled" if outcome == "canceled" else outcome
        if status not in {"pending", "succeeded", "canceled"}:
            status = "pending"
        provider_payment_id = f"{PROVIDER_PAYMENT_ID}-{len(self.calls)}"
        values: dict[str, object] = {
            "provider_payment_id": provider_payment_id,
            "status": status,
            "amount": payload["amount"]["value"],
            "currency": payload["amount"]["currency"],
            "metadata_order_id": int(payload["metadata"]["order_id"]),
            "payment_method": payload["payment_method_data"]["type"],
            "paid": status == "succeeded",
            "test": True,
            "provider_created_at": "2026-08-12T09:00:00Z",
        }
        if status == "pending":
            values["confirmation_url"] = "https://yoomoney.ru/checkout/payment/api-contract"
        elif status == "succeeded":
            values["captured_at"] = "2026-08-12T09:01:00Z"
        else:
            values["cancellation_party"] = "yoo_money"
            values["cancellation_reason"] = "payment_expired"
        return ProviderPaymentSnapshot.model_validate(values)

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        raise AssertionError(f"Unexpected provider GET for {provider_payment_id}")


def _seed_target(database: DatabaseManager) -> int:
    async def seed() -> int:
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                await IdentityRepository().ensure_system_authorization(session)
                product = Product(
                    title="Server catalog title",
                    price=Decimal("100.25"),
                    is_active=True,
                    stock_quantity=20,
                    sizes=["M"],
                    colors=["black"],
                    weight_kg=Decimal("0.500"),
                    height_cm=Decimal("10.00"),
                    width_cm=Decimal("20.00"),
                    length_cm=Decimal("30.00"),
                )
                product.variants.append(
                    ProductVariant(
                        size="M",
                        color="black",
                        sku="SKU-M-BLACK",
                        stock_quantity=20,
                    )
                )
                session.add_all(
                    [
                        product,
                        CatalogMigrationRun(
                            fingerprint_sha256=CATALOG_FINGERPRINT,
                            products_count=1,
                            variants_count=1,
                            media_count=0,
                            media_references_count=0,
                        ),
                        IdentityMigrationRun(
                            fingerprint_sha256=IDENTITY_FINGERPRINT,
                            users_count=0,
                        ),
                        OrderMigrationRun(
                            fingerprint_sha256=ORDER_FINGERPRINT,
                            orders_count=0,
                            items_count=0,
                            payment_references_count=0,
                            delivery_references_count=0,
                        ),
                    ]
                )
                await session.commit()
                return product.id
        finally:
            await database.shutdown()

    return asyncio.run(seed())


def _application(
    tmp_path: Path,
    provider: CheckoutProvider,
    *,
    legacy_app: FastAPI | None = None,
) -> tuple[FastAPI, DatabaseManager, int]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = _settings(tmp_path / "target.db")
    database = DatabaseManager(settings)
    product_id = _seed_target(database)
    provider_key_sequence = count(1)
    payment_service = PaymentService(
        settings,
        provider_key_factory=lambda: f"00000000-0000-4000-8000-{next(provider_key_sequence):012d}",
    )
    payment_creation = PaymentCreationService(
        settings,
        provider,
        payment_service=payment_service,
    )
    checkout = CheckoutService(
        settings,
        payment_creation,
        payment_service=payment_service,
    )
    storage = MinioStorage(settings, client=FakeMinioClient())
    return (
        create_app(
            settings=settings,
            database=database,
            storage=storage,
            legacy_app=legacy_app,
            checkout_service=checkout,
        ),
        database,
        product_id,
    )


def _headers(
    *, guest_token: str | None = None, key: str = "checkout_http_attempt_0001"
) -> dict[str, str]:
    headers = {"Idempotency-Key": key}
    if guest_token is not None:
        headers["X-Order-Access-Token"] = guest_token
    return headers


def test_target_checkout_overrides_legacy_and_replays_compatibility_response(
    tmp_path: Path,
) -> None:
    legacy = FastAPI()

    @legacy.post("/api/orders")
    async def legacy_checkout() -> dict[str, str]:
        return {"source": "legacy"}

    provider = CheckoutProvider()
    application, database, product_id = _application(
        tmp_path,
        provider,
        legacy_app=legacy,
    )
    guest_token = generate_order_guest_access_token()
    headers = _headers(guest_token=guest_token)

    with TestClient(application) as client:
        missing_capability = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(key="checkout_http_missing_capability"),
        )
        created = client.post("/api/orders", json=_command(product_id), headers=headers)
        replayed = client.post("/api/orders", json=_command(product_id), headers=headers)
        changed = client.post(
            "/api/orders",
            json=_command(product_id, phone="+7 900 000-00-01"),
            headers=headers,
        )
        schema = client.get("/openapi.json").json()

    assert missing_capability.status_code == 400
    assert missing_capability.headers["cache-control"] == "no-store"
    assert created.status_code == replayed.status_code == 200
    assert (
        created.json()
        == replayed.json()
        == {
            "order_id": created.json()["order_id"],
            "payment_url": "https://yoomoney.ru/checkout/payment/api-contract",
        }
    )
    assert created.headers["cache-control"] == "no-store"
    assert changed.status_code == 409
    assert changed.headers["cache-control"] == "no-store"
    assert len(provider.calls) == 1
    operation = schema["paths"]["/api/orders"]["post"]
    assert "application/json" in operation["requestBody"]["content"]
    idempotency_parameter = next(
        parameter for parameter in operation["parameters"] if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency_parameter["required"] is True

    async def counts() -> tuple[int, int, int]:
        await database.startup()
        try:
            async with database.session() as session:
                return (
                    int(await session.scalar(select(func.count()).select_from(Order)) or 0),
                    int(
                        await session.scalar(select(func.count()).select_from(OrderCreationRequest))
                        or 0
                    ),
                    int(
                        await session.scalar(select(func.count()).select_from(PaymentAttempt)) or 0
                    ),
                )
        finally:
            await database.shutdown()

    assert asyncio.run(counts()) == (1, 1, 1)


def test_checkout_rejects_untrusted_auth_body_and_business_inputs(tmp_path: Path) -> None:
    provider = CheckoutProvider()
    application, _, product_id = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()
    headers = _headers(guest_token=guest_token)

    with TestClient(application) as client:
        invalid_auth = client.post(
            "/api/orders",
            json=_command(product_id),
            headers={**headers, "Authorization": "Basic untrusted"},
        )
        invalid_json = client.post(
            "/api/orders",
            content=b'{"email":"secret@example.test"',
            headers={**headers, "Content-Type": "application/json"},
        )
        wrong_media = client.post(
            "/api/orders",
            content=b"checkout",
            headers={**headers, "Content-Type": "text/plain"},
        )
        oversized = client.post(
            "/api/orders",
            content=b"x" * (512 * 1024 + 1),
            headers={**headers, "Content-Type": "application/json"},
        )
        bad_key = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(guest_token=guest_token, key="short"),
        )
        bad_method = client.post(
            "/api/orders",
            json=_command(product_id, payment_method="cash"),
            headers=_headers(guest_token=guest_token, key="checkout_http_bad_method"),
        )
        bad_total = client.post(
            "/api/orders",
            json=_command(product_id, claimed_total_price="1.00"),
            headers=_headers(guest_token=guest_token, key="checkout_http_bad_total"),
        )
        bad_email = client.post(
            "/api/orders",
            json=_command(product_id, email="not-an-email"),
            headers=_headers(guest_token=guest_token, key="checkout_http_bad_email"),
        )
        out_of_stock = client.post(
            "/api/orders",
            json=_command(
                product_id,
                items=[
                    {
                        "id": "checkout-line-stock",
                        "product_id": product_id,
                        "price": "1.00",
                        "size": "M",
                        "color": "black",
                        "quantity": 21,
                    }
                ],
                claimed_total_price="2155.25",
            ),
            headers=_headers(guest_token=guest_token, key="checkout_http_no_stock"),
        )

    assert invalid_auth.status_code == 401
    assert invalid_auth.headers["cache-control"] == "no-store"
    assert invalid_json.status_code == 422
    assert "secret@example.test" not in invalid_json.text
    assert wrong_media.status_code == 415
    assert oversized.status_code == 413
    assert bad_key.status_code == 400
    assert bad_method.status_code == 400
    assert bad_total.status_code == 422
    assert bad_email.status_code == 422
    assert out_of_stock.status_code == 409
    assert all(
        response.headers["cache-control"] == "no-store"
        for response in (
            invalid_json,
            wrong_media,
            oversized,
            bad_key,
            bad_method,
            bad_total,
            bad_email,
            out_of_stock,
        )
    )
    assert provider.calls == []


def test_unknown_payment_outcome_is_safe_and_recovers_exactly_once(tmp_path: Path) -> None:
    provider = CheckoutProvider(outcomes=["timeout", "success"])
    application, _, product_id = _application(tmp_path, provider)
    headers = _headers(
        guest_token=generate_order_guest_access_token(),
        key="checkout_http_unknown_outcome",
    )

    with TestClient(application) as client:
        unknown = client.post("/api/orders", json=_command(product_id), headers=headers)
        recovered = client.post("/api/orders", json=_command(product_id), headers=headers)

    assert unknown.status_code == 503
    assert unknown.json()["detail"] == {
        "code": "payment_outcome_unknown",
        "order_id": recovered.json()["order_id"],
    }
    assert unknown.headers["retry-after"] == "2"
    assert unknown.headers["cache-control"] == "no-store"
    assert recovered.status_code == 200
    assert recovered.headers["cache-control"] == "no-store"
    assert len(provider.calls) == 2
    assert provider.calls[0] == provider.calls[1]


def test_known_payment_rejection_is_terminal_and_does_not_post_twice(tmp_path: Path) -> None:
    provider = CheckoutProvider(outcomes=["rejected"])
    application, _, product_id = _application(tmp_path, provider)
    headers = _headers(
        guest_token=generate_order_guest_access_token(),
        key="checkout_http_known_rejection",
    )

    with TestClient(application) as client:
        rejected = client.post("/api/orders", json=_command(product_id), headers=headers)
        replayed = client.post("/api/orders", json=_command(product_id), headers=headers)

    assert rejected.status_code == replayed.status_code == 502
    assert rejected.json() == replayed.json()
    assert rejected.json()["detail"]["code"] == "payment_rejected"
    assert rejected.headers["cache-control"] == "no-store"
    assert len(provider.calls) == 1


def _latest_otp(target_path: Path) -> str:
    with sqlite3.connect(target_path) as connection:
        row = connection.execute(
            """
            SELECT payload_ciphertext, payload_nonce, payload_tag,
                   encryption_key_version
            FROM notification_outbox
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    assert row is not None
    payload = NotificationPayloadCodec.from_base64_key(NOTIFICATION_KEY).decrypt(
        EncryptedNotificationPayload(
            ciphertext=row[0],
            nonce=row[1],
            tag=row[2],
            key_version=row[3],
        )
    )
    return str(payload["code"])


def test_authenticated_checkout_uses_resolved_identity_without_guest_capability(
    tmp_path: Path,
) -> None:
    provider = CheckoutProvider()
    application, _, product_id = _application(tmp_path, provider)
    database_path = tmp_path / "target.db"

    with TestClient(application) as client:
        requested = client.post(
            "/api/auth/email/request",
            json={"email": "account@example.test"},
        )
        assert requested.status_code == 200
        verified = client.post(
            "/api/auth/email/verify",
            json={"email": "account@example.test", "code": _latest_otp(database_path)},
        )
        assert verified.status_code == 200
        authorization = {"Authorization": f"Bearer {verified.json()['token']}"}
        created = client.post(
            "/api/orders",
            json=_command(product_id),
            headers={
                **authorization,
                **_headers(key="checkout_http_authenticated"),
            },
        )
        mixed_actor = client.post(
            "/api/orders",
            json=_command(product_id),
            headers={
                **authorization,
                **_headers(
                    guest_token=generate_order_guest_access_token(),
                    key="checkout_http_mixed_actor",
                ),
            },
        )

    assert created.status_code == 200
    assert created.headers["cache-control"] == "no-store"
    assert mixed_actor.status_code == 400
    assert mixed_actor.headers["cache-control"] == "no-store"
    assert len(provider.calls) == 1


def test_disabled_checkout_preserves_legacy_order_write(tmp_path: Path) -> None:
    legacy = FastAPI()

    @legacy.post("/api/orders")
    async def legacy_checkout() -> dict[str, str]:
        return {"source": "legacy"}

    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=False,
        checkout_v2_enabled=False,
    )
    application = create_app(settings=settings, legacy_app=legacy)

    with TestClient(application) as client:
        response = client.post("/api/orders", json={"legacy": True})
        retry = client.post(
            "/api/orders/1/payment-attempts",
            headers={"Idempotency-Key": "disabled_payment_retry"},
        )

    assert response.status_code == 200
    assert response.json() == {"source": "legacy"}
    assert retry.status_code == 404


def test_factory_owns_target_checkout_provider_transport_lifecycle(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "target.db")
    database = DatabaseManager(settings)
    _seed_target(database)
    storage = MinioStorage(settings, client=FakeMinioClient())
    application = create_app(
        settings=settings,
        database=database,
        storage=storage,
    )
    checkout = application.state.checkout_service
    transport = checkout.payment_creation_service.provider.transport

    assert isinstance(transport, AiohttpYooKassaTransport)
    assert transport._session is None
    with TestClient(application) as client:
        assert client.get("/health/ready").status_code == 200
        assert transport._session is not None
    assert transport._session is None


def test_guest_payment_retry_creates_one_later_attempt_and_replays(tmp_path: Path) -> None:
    provider = CheckoutProvider(outcomes=["rejected", "success"])
    application, database, product_id = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()

    with TestClient(application) as client:
        checkout = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(
                guest_token=guest_token,
                key="checkout_before_payment_retry",
            ),
        )
        assert checkout.status_code == 502
        order_id = checkout.json()["detail"]["order_id"]
        retry_url = f"/api/orders/{order_id}/payment-attempts"
        retry_headers = _headers(
            guest_token=guest_token,
            key="payment_retry_attempt_0001",
        )
        retried = client.post(retry_url, headers=retry_headers)
        replayed = client.post(retry_url, headers=retry_headers)
        new_while_active = client.post(
            retry_url,
            headers=_headers(
                guest_token=guest_token,
                key="payment_retry_attempt_0002",
            ),
        )
        operation = client.get("/openapi.json").json()["paths"][
            retry_url.replace(str(order_id), "{order_id}")
        ]["post"]

    assert retried.status_code == replayed.status_code == 200
    assert (
        retried.json()
        == replayed.json()
        == {
            "order_id": order_id,
            "payment_url": "https://yoomoney.ru/checkout/payment/api-contract",
        }
    )
    assert retried.headers["cache-control"] == "no-store"
    assert new_while_active.status_code == 409
    assert new_while_active.headers["cache-control"] == "no-store"
    assert (
        next(
            parameter
            for parameter in operation["parameters"]
            if parameter["name"] == "Idempotency-Key"
        )["required"]
        is True
    )
    assert len(provider.calls) == 2
    assert provider.calls[0][0] != provider.calls[1][0]
    assert provider.calls[0][1] == provider.calls[1][1]

    async def counts() -> tuple[int, int, list[int], list[int]]:
        await database.startup()
        try:
            async with database.session() as session:
                attempts = list(
                    await session.scalars(
                        select(PaymentAttempt).order_by(PaymentAttempt.attempt_number)
                    )
                )
                reservation_versions = list(
                    await session.scalars(
                        select(InventoryReservation.version).order_by(InventoryReservation.id)
                    )
                )
                return (
                    int(await session.scalar(select(func.count()).select_from(Order)) or 0),
                    len(attempts),
                    [attempt.attempt_number for attempt in attempts],
                    reservation_versions,
                )
        finally:
            await database.shutdown()

    assert asyncio.run(counts()) == (1, 2, [1, 2], [2])


def test_payment_retry_authorization_and_empty_body_fail_closed(tmp_path: Path) -> None:
    provider = CheckoutProvider(outcomes=["rejected", "success"])
    application, _, product_id = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()

    with TestClient(application) as client:
        checkout = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(
                guest_token=guest_token,
                key="checkout_before_guarded_retry",
            ),
        )
        order_id = checkout.json()["detail"]["order_id"]
        retry_url = f"/api/orders/{order_id}/payment-attempts"
        missing_capability = client.post(
            retry_url,
            headers=_headers(key="payment_retry_missing_capability"),
        )
        wrong_capability = client.post(
            retry_url,
            headers=_headers(
                guest_token=generate_order_guest_access_token(),
                key="payment_retry_wrong_capability",
            ),
        )
        malformed_capability = client.post(
            retry_url,
            headers=_headers(
                guest_token="invalid",
                key="payment_retry_bad_capability",
            ),
        )
        invalid_auth = client.post(
            retry_url,
            headers={
                **_headers(
                    guest_token=guest_token,
                    key="payment_retry_invalid_auth",
                ),
                "Authorization": "Basic untrusted",
            },
        )
        unexpected_body = client.post(
            retry_url,
            json={"email": "secret@example.test"},
            headers=_headers(
                guest_token=guest_token,
                key="payment_retry_unexpected_body",
            ),
        )
        invalid_key = client.post(
            retry_url,
            headers=_headers(guest_token=guest_token, key="short"),
        )
        invalid_order = client.post(
            "/api/orders/01/payment-attempts",
            headers=_headers(
                guest_token=guest_token,
                key="payment_retry_invalid_order",
            ),
        )
        recovered = client.post(
            retry_url,
            headers=_headers(
                guest_token=guest_token,
                key="payment_retry_after_guards",
            ),
        )

    assert checkout.status_code == 502
    assert missing_capability.status_code == 404
    assert wrong_capability.status_code == 404
    assert malformed_capability.status_code == 404
    assert invalid_auth.status_code == 401
    assert unexpected_body.status_code == 400
    assert "secret@example.test" not in unexpected_body.text
    assert invalid_key.status_code == 400
    assert invalid_order.status_code == 404
    assert recovered.status_code == 200
    assert all(
        response.headers["cache-control"] == "no-store"
        for response in (
            missing_capability,
            wrong_capability,
            malformed_capability,
            invalid_auth,
            unexpected_body,
            invalid_key,
            invalid_order,
            recovered,
        )
    )
    assert len(provider.calls) == 2


def test_payment_retry_unknown_outcome_recovers_same_attempt(tmp_path: Path) -> None:
    provider = CheckoutProvider(outcomes=["rejected", "timeout", "success"])
    application, _, product_id = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()

    with TestClient(application) as client:
        checkout = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(
                guest_token=guest_token,
                key="checkout_before_unknown_retry",
            ),
        )
        order_id = checkout.json()["detail"]["order_id"]
        retry_url = f"/api/orders/{order_id}/payment-attempts"
        retry_headers = _headers(
            guest_token=guest_token,
            key="payment_retry_unknown_attempt",
        )
        unknown = client.post(retry_url, headers=retry_headers)
        recovered = client.post(retry_url, headers=retry_headers)

    assert unknown.status_code == 503
    assert unknown.json()["detail"] == {
        "code": "payment_outcome_unknown",
        "order_id": order_id,
    }
    assert unknown.headers["retry-after"] == "2"
    assert recovered.status_code == 200
    assert len(provider.calls) == 3
    assert provider.calls[1] == provider.calls[2]


def test_payment_retry_known_rejection_is_terminal_and_not_posted_twice(
    tmp_path: Path,
) -> None:
    provider = CheckoutProvider(outcomes=["rejected", "rejected"])
    application, _, product_id = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()

    with TestClient(application) as client:
        checkout = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(
                guest_token=guest_token,
                key="checkout_before_rejected_retry",
            ),
        )
        order_id = checkout.json()["detail"]["order_id"]
        retry_url = f"/api/orders/{order_id}/payment-attempts"
        retry_headers = _headers(
            guest_token=guest_token,
            key="payment_retry_known_rejection",
        )
        rejected = client.post(retry_url, headers=retry_headers)
        replayed = client.post(retry_url, headers=retry_headers)

    assert rejected.status_code == replayed.status_code == 502
    assert (
        rejected.json()
        == replayed.json()
        == {"detail": {"code": "payment_rejected", "order_id": order_id}}
    )
    assert len(provider.calls) == 2


def test_canceled_payment_can_retry_but_succeeded_checkout_only_replays(
    tmp_path: Path,
) -> None:
    canceled_provider = CheckoutProvider(outcomes=["canceled", "success"])
    canceled_app, _, product_id = _application(tmp_path / "canceled", canceled_provider)
    canceled_guest_token = generate_order_guest_access_token()

    with TestClient(canceled_app) as client:
        canceled = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(
                guest_token=canceled_guest_token,
                key="checkout_canceled_before_retry",
            ),
        )
        retried = client.post(
            f"/api/orders/{canceled.json()['order_id']}/payment-attempts",
            headers=_headers(
                guest_token=canceled_guest_token,
                key="payment_retry_after_canceled",
            ),
        )

    assert canceled.status_code == 200 and canceled.json()["payment_url"] is None
    assert retried.status_code == 200
    assert len(canceled_provider.calls) == 2

    succeeded_provider = CheckoutProvider(outcomes=["succeeded"])
    succeeded_app, _, succeeded_product_id = _application(
        tmp_path / "succeeded",
        succeeded_provider,
    )
    succeeded_guest_token = generate_order_guest_access_token()
    checkout_headers = _headers(
        guest_token=succeeded_guest_token,
        key="checkout_succeeded_exact_replay",
    )

    with TestClient(succeeded_app) as client:
        succeeded = client.post(
            "/api/orders",
            json=_command(succeeded_product_id),
            headers=checkout_headers,
        )
        replayed = client.post(
            "/api/orders",
            json=_command(succeeded_product_id),
            headers=checkout_headers,
        )
        new_retry = client.post(
            f"/api/orders/{succeeded.json()['order_id']}/payment-attempts",
            headers=_headers(
                guest_token=succeeded_guest_token,
                key="payment_retry_after_succeeded",
            ),
        )

    assert succeeded.status_code == replayed.status_code == 200
    assert succeeded.json() == replayed.json()
    assert succeeded.json()["payment_url"] is None
    assert new_retry.status_code == 409
    assert len(succeeded_provider.calls) == 1


def test_expired_reservation_cannot_start_later_payment_attempt(tmp_path: Path) -> None:
    provider = CheckoutProvider(outcomes=["rejected"])
    application, _, product_id = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()

    with TestClient(application) as client:
        checkout = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(
                guest_token=guest_token,
                key="checkout_before_expired_retry",
            ),
        )
        order_id = checkout.json()["detail"]["order_id"]
        with sqlite3.connect(tmp_path / "target.db") as connection:
            connection.execute(
                "UPDATE inventory_reservations SET expires_at = ? WHERE order_id = ?",
                ("2020-01-01T00:00:00+00:00", order_id),
            )
            connection.commit()
        expired = client.post(
            f"/api/orders/{order_id}/payment-attempts",
            headers=_headers(
                guest_token=guest_token,
                key="payment_retry_expired_reservation",
            ),
        )

    assert expired.status_code == 409
    assert expired.headers["cache-control"] == "no-store"
    assert len(provider.calls) == 1


def test_authenticated_payment_retry_requires_direct_order_owner(tmp_path: Path) -> None:
    provider = CheckoutProvider(outcomes=["rejected", "success"])
    application, _, product_id = _application(tmp_path, provider)
    database_path = tmp_path / "target.db"

    with TestClient(application) as client:
        assert (
            client.post(
                "/api/auth/email/request",
                json={"email": "owner@example.test"},
            ).status_code
            == 200
        )
        owner_session = client.post(
            "/api/auth/email/verify",
            json={"email": "owner@example.test", "code": _latest_otp(database_path)},
        )
        owner_auth = {"Authorization": f"Bearer {owner_session.json()['token']}"}
        checkout = client.post(
            "/api/orders",
            json=_command(product_id),
            headers={
                **owner_auth,
                **_headers(key="checkout_owner_before_payment_retry"),
            },
        )
        order_id = checkout.json()["detail"]["order_id"]

        assert (
            client.post(
                "/api/auth/email/request",
                json={"email": "intruder@example.test"},
            ).status_code
            == 200
        )
        intruder_session = client.post(
            "/api/auth/email/verify",
            json={"email": "intruder@example.test", "code": _latest_otp(database_path)},
        )
        intruder_auth = {"Authorization": f"Bearer {intruder_session.json()['token']}"}
        retry_url = f"/api/orders/{order_id}/payment-attempts"
        not_owned = client.post(
            retry_url,
            headers={
                **intruder_auth,
                **_headers(key="payment_retry_intruder_attempt"),
            },
        )
        mixed_actor = client.post(
            retry_url,
            headers={
                **owner_auth,
                **_headers(
                    guest_token=generate_order_guest_access_token(),
                    key="payment_retry_mixed_owner_attempt",
                ),
            },
        )
        retried = client.post(
            retry_url,
            headers={
                **owner_auth,
                **_headers(key="payment_retry_owner_attempt"),
            },
        )

    assert checkout.status_code == 502
    assert not_owned.status_code == 404
    assert not_owned.headers["cache-control"] == "no-store"
    assert mixed_actor.status_code == 400
    assert mixed_actor.headers["cache-control"] == "no-store"
    assert retried.status_code == 200
    assert retried.json()["order_id"] == order_id
    assert len(provider.calls) == 2


def test_revoked_guest_capability_cannot_authorize_payment_retry(tmp_path: Path) -> None:
    provider = CheckoutProvider(outcomes=["rejected"])
    application, _, product_id = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()

    with TestClient(application) as client:
        checkout = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(
                guest_token=guest_token,
                key="checkout_before_revoked_retry",
            ),
        )
        order_id = checkout.json()["detail"]["order_id"]
        with sqlite3.connect(tmp_path / "target.db") as connection:
            connection.execute(
                "UPDATE order_guest_access SET revoked_at = created_at WHERE order_id = ?",
                (order_id,),
            )
            connection.commit()
        revoked = client.post(
            f"/api/orders/{order_id}/payment-attempts",
            headers=_headers(
                guest_token=guest_token,
                key="payment_retry_revoked_capability",
            ),
        )

    assert revoked.status_code == 404
    assert revoked.headers["cache-control"] == "no-store"
    assert len(provider.calls) == 1


def test_payment_retry_attempt_count_is_bounded_per_order(tmp_path: Path) -> None:
    provider = CheckoutProvider(outcomes=["rejected", "rejected", "rejected"])
    application, _, product_id = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()

    with TestClient(application) as client:
        checkout = client.post(
            "/api/orders",
            json=_command(product_id),
            headers=_headers(
                guest_token=guest_token,
                key="checkout_before_bounded_retries",
            ),
        )
        order_id = checkout.json()["detail"]["order_id"]
        retry_url = f"/api/orders/{order_id}/payment-attempts"
        second = client.post(
            retry_url,
            headers=_headers(
                guest_token=guest_token,
                key="payment_retry_bounded_attempt_2",
            ),
        )
        third = client.post(
            retry_url,
            headers=_headers(
                guest_token=guest_token,
                key="payment_retry_bounded_attempt_3",
            ),
        )
        exhausted = client.post(
            retry_url,
            headers=_headers(
                guest_token=guest_token,
                key="payment_retry_bounded_attempt_4",
            ),
        )

    assert checkout.status_code == second.status_code == third.status_code == 502
    assert exhausted.status_code == 409
    assert exhausted.headers["cache-control"] == "no-store"
    assert len(provider.calls) == 3
