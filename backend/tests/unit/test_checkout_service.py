from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product, ProductVariant
from app.modules.checkout.security import derive_checkout_payment_attempt_key
from app.modules.checkout.service import (
    CheckoutActorError,
    CheckoutDisabledError,
    CheckoutPaymentError,
    CheckoutPaymentMethodError,
    CheckoutService,
)
from app.modules.fulfillment.models import FulfillmentJob
from app.modules.identity.models import User
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import (
    Order,
    OrderCreationRequest,
    OrderGuestAccess,
)
from app.modules.orders.schemas import OrderCreationCommand
from app.modules.orders.security import generate_order_guest_access_token
from app.modules.payments.creation import PaymentCreationService
from app.modules.payments.models import Payment, PaymentAttempt, PaymentReconciliationJob
from app.modules.payments.provider import YooKassaProviderError
from app.modules.payments.schemas import ProviderPaymentSnapshot
from app.modules.payments.security import PAYMENT_ATTEMPT_KEY_PATTERN
from app.modules.payments.service import PaymentService

PROVIDER_KEY = "00000000-0000-4000-8000-000000000001"
PROVIDER_PAYMENT_ID = "2c111111-000f-5000-a000-111111111111"


def _settings(
    path: Path,
    *,
    checkout_enabled: bool = True,
    fulfillment_enabled: bool = False,
) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        public_base_url="https://shop.example.test",
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.example.test",
        catalog_reads_enabled=True,
        catalog_migration_fingerprint="a" * 64,
        identity_api_enabled=True,
        identity_migration_fingerprint="b" * 64,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key="bm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm4=",
        order_reads_enabled=True,
        order_migration_fingerprint="c" * 64,
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
        fulfillment_outbox_enabled=fulfillment_enabled,
    )


def _command(
    product_id: int,
    *,
    payment_method: str = "card",
) -> OrderCreationCommand:
    return OrderCreationCommand.model_validate(
        {
            "email": "customer@example.test",
            "phone": "+7 900 000-00-00",
            "first_name": "Customer",
            "delivery_city": "Moscow",
            "delivery_method": "cdek_pickup",
            "delivery_address": "Moscow pickup point",
            "cdek_point_code": "MSK1",
            "payment_method": payment_method,
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
                    "customization": {"fit": "regular"},
                }
            ],
            "claimed_total_price": "250.50",
            "delivery_price": "50.00",
            "currency": "RUB",
        }
    )


def _snapshot(
    order_id: int,
    *,
    status: str = "pending",
    payment_method: str = "bank_card",
) -> ProviderPaymentSnapshot:
    values: dict[str, object] = {
        "provider_payment_id": PROVIDER_PAYMENT_ID,
        "status": status,
        "amount": "250.50",
        "currency": "RUB",
        "metadata_order_id": order_id,
        "payment_method": payment_method,
        "paid": status in {"waiting_for_capture", "succeeded"},
        "test": True,
        "provider_created_at": "2026-08-12T09:00:00Z",
    }
    if status == "pending":
        values["confirmation_url"] = "https://yoomoney.ru/checkout/payment/checkout-1"
    if status == "succeeded":
        values["captured_at"] = "2026-08-12T09:01:00Z"
    return ProviderPaymentSnapshot.model_validate(values)


async def _seed_catalog(database: DatabaseManager) -> int:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        product = Product(
            title="Server catalog title",
            price=Decimal("100.25"),
            is_active=True,
            stock_quantity=7,
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
                stock_quantity=5,
            )
        )
        session.add(product)
        await session.commit()
        return product.id


@dataclass
class ObservingProvider:
    database: DatabaseManager
    outcomes: list[ProviderPaymentSnapshot | Exception]
    calls: list[tuple[str, bytes]] = field(default_factory=list)

    async def create_payment(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> ProviderPaymentSnapshot:
        self.calls.append((idempotence_key, request_body))
        async with self.database.session() as observer:
            assert int(await observer.scalar(select(func.count()).select_from(Order)) or 0) == 1
            assert (
                int(await observer.scalar(select(func.count()).select_from(PaymentAttempt)) or 0)
                == 1
            )
            reservation = await observer.scalar(select(InventoryReservation))
            assert reservation is not None and reservation.status == "active"
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        raise AssertionError(f"Unexpected provider GET for {provider_payment_id}")


class FailingPaymentPreparation:
    async def prepare_attempt(
        self,
        session,
        *,
        order_id: int,
        client_attempt_key: str,
        capture_mode: str = "automatic",
    ):
        del session, order_id, client_attempt_key, capture_mode
        raise RuntimeError("synthetic payment preparation failure")


def _checkout_service(
    settings: Settings,
    provider: ObservingProvider,
) -> CheckoutService:
    payment_service = PaymentService(
        settings,
        provider_key_factory=lambda: PROVIDER_KEY,
    )
    payment_creation = PaymentCreationService(
        settings,
        provider,
        payment_service=payment_service,
    )
    return CheckoutService(
        settings,
        payment_creation,
        payment_service=payment_service,
    )


def test_guest_checkout_commits_each_phase_and_replays_without_duplicates(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "guest-checkout.db"))
        await database.startup()
        try:
            product_id = await _seed_catalog(database)
            guest_token = generate_order_guest_access_token()
            provider = ObservingProvider(database, [])
            service = _checkout_service(database.settings, provider)

            async with database.session() as session:
                order = await service.order_creation_service.create(
                    session,
                    idempotency_key="target_checkout_attempt_0001",
                    command=_command(product_id),
                    guest_access_token=guest_token,
                )
                await session.commit()
            provider.outcomes.append(_snapshot(order.order_id))

            async with database.session() as session:
                created = await service.checkout(
                    session,
                    idempotency_key="target_checkout_attempt_0001",
                    command=_command(product_id),
                    guest_access_token=guest_token,
                )
            assert created.order_id == order.order_id
            assert created.order_replayed
            assert created.payment_attempt_status == "pending"
            assert created.payment_attempt_number == 1
            assert created.payment_url == ("https://yoomoney.ru/checkout/payment/checkout-1")
            assert len(provider.calls) == 1

            async with database.session() as session:
                replayed = await service.checkout(
                    session,
                    idempotency_key="target_checkout_attempt_0001",
                    command=_command(product_id),
                    guest_access_token=guest_token,
                )
            assert replayed.order_replayed and replayed.payment_replayed
            assert replayed.order_id == created.order_id
            assert replayed.payment_attempt_id == created.payment_attempt_id
            assert len(provider.calls) == 1

            async with database.session() as session:
                counts = {
                    "orders": await session.scalar(select(func.count()).select_from(Order)),
                    "requests": await session.scalar(
                        select(func.count()).select_from(OrderCreationRequest)
                    ),
                    "reservations": await session.scalar(
                        select(func.count()).select_from(InventoryReservation)
                    ),
                    "payments": await session.scalar(select(func.count()).select_from(Payment)),
                    "attempts": await session.scalar(
                        select(func.count()).select_from(PaymentAttempt)
                    ),
                    "jobs": await session.scalar(
                        select(func.count()).select_from(PaymentReconciliationJob)
                    ),
                }
                assert counts == {
                    "orders": 1,
                    "requests": 1,
                    "reservations": 1,
                    "payments": 1,
                    "attempts": 1,
                    "jobs": 1,
                }
                request = await session.scalar(select(OrderCreationRequest))
                access = await session.scalar(select(OrderGuestAccess))
                attempt = await session.scalar(select(PaymentAttempt))
                assert request is not None and access is not None and attempt is not None
                persisted = repr(
                    {
                        **request.__dict__,
                        **access.__dict__,
                        **attempt.__dict__,
                    }
                )
                assert "target_checkout_attempt_0001" not in persisted
                assert guest_token not in persisted
                assert (
                    derive_checkout_payment_attempt_key("target_checkout_attempt_0001")
                    not in persisted
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_unknown_provider_outcome_replays_exact_checkout_without_new_order(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "unknown-checkout.db"))
        await database.startup()
        try:
            product_id = await _seed_catalog(database)
            guest_token = generate_order_guest_access_token()
            provider = ObservingProvider(
                database,
                [
                    YooKassaProviderError(
                        "timeout",
                        retryable=True,
                        outcome_unknown=True,
                    )
                ],
            )
            service = _checkout_service(database.settings, provider)

            with pytest.raises(CheckoutPaymentError) as failed:
                async with database.session() as session:
                    await service.checkout(
                        session,
                        idempotency_key="target_checkout_attempt_0002",
                        command=_command(product_id),
                        guest_access_token=guest_token,
                    )
            assert failed.value.code == "timeout"
            assert failed.value.outcome_unknown
            assert failed.value.order_id > 0 and failed.value.payment_attempt_id > 0

            provider.outcomes.append(_snapshot(failed.value.order_id))
            async with database.session() as session:
                recovered = await service.checkout(
                    session,
                    idempotency_key="target_checkout_attempt_0002",
                    command=_command(product_id),
                    guest_access_token=guest_token,
                )
            assert recovered.order_replayed and recovered.payment_replayed
            assert recovered.payment_attempt_status == "pending"
            assert len(provider.calls) == 2
            assert provider.calls[0] == provider.calls[1]

            async with database.session() as session:
                assert int(await session.scalar(select(func.count()).select_from(Order)) or 0) == 1
                assert (
                    int(await session.scalar(select(func.count()).select_from(PaymentAttempt)) or 0)
                    == 1
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_payment_preparation_failure_rolls_back_order_reservation_and_guest_access(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "atomic-prepare.db"))
        await database.startup()
        try:
            product_id = await _seed_catalog(database)
            provider = ObservingProvider(database, [])
            real_payment_service = PaymentService(
                database.settings,
                provider_key_factory=lambda: PROVIDER_KEY,
            )
            payment_creation = PaymentCreationService(
                database.settings,
                provider,
                payment_service=real_payment_service,
            )
            service = CheckoutService(
                database.settings,
                payment_creation,
                payment_service=FailingPaymentPreparation(),
            )

            with pytest.raises(RuntimeError, match="synthetic"):
                async with database.session() as session:
                    await service.checkout(
                        session,
                        idempotency_key="target_checkout_attempt_atomic",
                        command=_command(product_id),
                        guest_access_token=generate_order_guest_access_token(),
                    )

            async with database.session() as session:
                for model in (
                    Order,
                    OrderCreationRequest,
                    OrderGuestAccess,
                    InventoryReservation,
                    Payment,
                    PaymentAttempt,
                ):
                    assert (
                        int(await session.scalar(select(func.count()).select_from(model)) or 0) == 0
                    )
                product = await session.get(Product, product_id)
                variant = await session.scalar(select(ProductVariant))
                assert product is not None and product.reserved_quantity == 0
                assert variant is not None and variant.reserved_quantity == 0
            assert provider.calls == []
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_authenticated_checkout_owns_order_without_guest_capability(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "account-checkout.db"))
        await database.startup()
        try:
            product_id = await _seed_catalog(database)
            async with database.session() as session:
                user = User(
                    email="owner@example.test",
                    email_normalized="owner@example.test",
                    status="active",
                    email_verified_at=None,
                )
                session.add(user)
                await session.commit()
                user_id = user.id
            provider = ObservingProvider(database, [])
            service = _checkout_service(database.settings, provider)

            command = _command(product_id)
            provider.outcomes.append(_snapshot(1, status="succeeded"))
            async with database.session() as session:
                result = await service.checkout(
                    session,
                    idempotency_key="target_checkout_attempt_0003",
                    command=command,
                    user_id=user_id,
                )
            assert result.order_status == "processing"
            assert result.order_payment_status == "paid"
            assert result.payment_attempt_status == "succeeded"
            assert result.payment_url is None

            async with database.session() as session:
                order = await session.get(Order, result.order_id)
                access = await session.scalar(select(OrderGuestAccess))
                reservation = await session.scalar(select(InventoryReservation))
                product = await session.get(Product, product_id)
                assert order is not None and order.user_id == user_id
                assert access is None
                assert reservation is not None and reservation.status == "confirmed"
                assert product is not None
                assert product.stock_quantity == 5 and product.reserved_quantity == 0
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_succeeded_checkout_atomically_schedules_pii_free_fulfillment_jobs(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = DatabaseManager(
            _settings(
                tmp_path / "fulfilled-checkout.db",
                fulfillment_enabled=True,
            )
        )
        await database.startup()
        try:
            product_id = await _seed_catalog(database)
            provider = ObservingProvider(database, [_snapshot(1, status="succeeded")])
            service = _checkout_service(database.settings, provider)
            guest_token = generate_order_guest_access_token()

            async with database.session() as session:
                result = await service.checkout(
                    session,
                    idempotency_key="target_checkout_fulfillment_0001",
                    command=_command(product_id),
                    guest_access_token=guest_token,
                )
            assert result.order_status == "processing"
            assert result.order_payment_status == "paid"

            async with database.session() as session:
                jobs = list(
                    await session.scalars(select(FulfillmentJob).order_by(FulfillmentJob.kind))
                )
                assert {job.kind for job in jobs} == {
                    "cdek_order_create",
                    "crm_order_project",
                    "customer_payment_email",
                }
                assert {job.order_id for job in jobs} == {result.order_id}
                assert {job.source_payment_attempt_id for job in jobs} == {
                    result.payment_attempt_id
                }
                assert {job.status for job in jobs} == {"pending"}
                assert {job.max_attempts for job in jobs} == {5}
                persisted = repr([job.__dict__ for job in jobs])
                for secret in (
                    "customer@example.test",
                    "+7 900 000-00-00",
                    "Moscow pickup point",
                    guest_token,
                ):
                    assert secret not in persisted

            async with database.session() as session:
                replay = await service.checkout(
                    session,
                    idempotency_key="target_checkout_fulfillment_0001",
                    command=_command(product_id),
                    guest_access_token=guest_token,
                )
            assert replay.payment_replayed
            assert len(provider.calls) == 1
            async with database.session() as session:
                assert (
                    int(await session.scalar(select(func.count()).select_from(FulfillmentJob)) or 0)
                    == 3
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_checkout_guards_actor_method_and_default_off_before_writes(tmp_path: Path) -> None:
    async def scenario() -> None:
        enabled_database = DatabaseManager(_settings(tmp_path / "checkout-guards.db"))
        await enabled_database.startup()
        try:
            product_id = await _seed_catalog(enabled_database)
            provider = ObservingProvider(enabled_database, [])
            service = _checkout_service(enabled_database.settings, provider)
            command = _command(product_id)

            with pytest.raises(CheckoutActorError, match="Guest"):
                async with enabled_database.session() as session:
                    await service.checkout(
                        session,
                        idempotency_key="target_checkout_attempt_0004",
                        command=command,
                    )
            with pytest.raises(CheckoutActorError, match="Authenticated"):
                async with enabled_database.session() as session:
                    await service.checkout(
                        session,
                        idempotency_key="target_checkout_attempt_0005",
                        command=command,
                        user_id=1,
                        guest_access_token=generate_order_guest_access_token(),
                    )
            with pytest.raises(CheckoutPaymentMethodError):
                async with enabled_database.session() as session:
                    await service.checkout(
                        session,
                        idempotency_key="target_checkout_attempt_0006",
                        command=_command(product_id, payment_method="cash"),
                        guest_access_token=generate_order_guest_access_token(),
                    )
            assert provider.calls == []
            async with enabled_database.session() as session:
                assert int(await session.scalar(select(func.count()).select_from(Order)) or 0) == 0
        finally:
            await enabled_database.shutdown()

        disabled_database = DatabaseManager(
            _settings(tmp_path / "checkout-disabled.db", checkout_enabled=False)
        )
        await disabled_database.startup()
        try:
            product_id = await _seed_catalog(disabled_database)
            provider = ObservingProvider(disabled_database, [])
            service = _checkout_service(disabled_database.settings, provider)
            with pytest.raises(CheckoutDisabledError):
                async with disabled_database.session() as session:
                    await service.checkout(
                        session,
                        idempotency_key="target_checkout_attempt_0007",
                        command=_command(product_id),
                        guest_access_token=generate_order_guest_access_token(),
                    )
            assert provider.calls == []
        finally:
            await disabled_database.shutdown()

    asyncio.run(scenario())


def test_qr_checkout_maps_to_sbp_provider_request(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "qr-checkout.db"))
        await database.startup()
        try:
            product_id = await _seed_catalog(database)
            provider = ObservingProvider(database, [])
            service = _checkout_service(database.settings, provider)
            provider.outcomes.append(_snapshot(1, payment_method="sbp"))

            async with database.session() as session:
                result = await service.checkout(
                    session,
                    idempotency_key="target_checkout_attempt_0010",
                    command=_command(product_id, payment_method="qr"),
                    guest_access_token=generate_order_guest_access_token(),
                )
            assert result.payment_attempt_status == "pending"
            assert len(provider.calls) == 1
            request = json.loads(provider.calls[0][1])
            assert request["payment_method_data"] == {"type": "sbp"}
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_known_provider_rejection_keeps_one_failed_attempt_for_operator_action(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "rejected-checkout.db"))
        await database.startup()
        try:
            product_id = await _seed_catalog(database)
            provider = ObservingProvider(
                database,
                [YooKassaProviderError("request_rejected", retryable=False)],
            )
            service = _checkout_service(database.settings, provider)
            guest_token = generate_order_guest_access_token()

            for _ in range(2):
                with pytest.raises(CheckoutPaymentError) as rejected:
                    async with database.session() as session:
                        await service.checkout(
                            session,
                            idempotency_key="target_checkout_attempt_0011",
                            command=_command(product_id),
                            guest_access_token=guest_token,
                        )
                assert rejected.value.code == "request_rejected"
                assert not rejected.value.outcome_unknown

            assert len(provider.calls) == 1
            async with database.session() as session:
                order = await session.scalar(select(Order))
                attempt = await session.scalar(select(PaymentAttempt))
                reservation = await session.scalar(select(InventoryReservation))
                assert order is not None and order.status == "new"
                assert order.payment_status == "pending"
                assert attempt is not None and attempt.status == "failed"
                assert attempt.resolved_at is not None
                assert reservation is not None and reservation.status == "active"
                assert int(await session.scalar(select(func.count()).select_from(Order)) or 0) == 1
                assert (
                    int(await session.scalar(select(func.count()).select_from(PaymentAttempt)) or 0)
                    == 1
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_checkout_payment_key_derivation_is_stable_and_provider_safe() -> None:
    first = derive_checkout_payment_attempt_key("target_checkout_attempt_0008")
    replay = derive_checkout_payment_attempt_key("target_checkout_attempt_0008")
    other = derive_checkout_payment_attempt_key("target_checkout_attempt_0009")

    assert first == replay
    assert first != other
    assert len(first) == 43
    assert PAYMENT_ATTEMPT_KEY_PATTERN.fullmatch(first)
    assert "target_checkout_attempt_0008" not in first
    assert json.dumps({"key": first})
