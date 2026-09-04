from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.models import User
from app.modules.orders.models import Order
from app.modules.payments.models import Payment, PaymentAttempt, PaymentOperation
from app.modules.payments.operation_service import (
    PaymentOperationConflictError,
    PaymentOperationFailedError,
    PaymentOperationService,
)
from app.modules.payments.provider import YooKassaProviderError
from app.modules.payments.schemas import ProviderPaymentSnapshot
from app.modules.payments.service import PaymentService

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
PROVIDER_KEY = "00000000-0000-4000-8000-000000000099"
PROVIDER_PAYMENT_ID = "2c111111-000f-5000-a000-111111111111"


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        public_base_url="https://shop.example.test",
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        identity_api_enabled=True,
        identity_migration_fingerprint="a" * 64,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key="bm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm4=",
        yookassa_shop_id="shop-id",
        yookassa_api_key="payment-secret",
        payment_creation_enabled=True,
        payment_management_enabled=True,
        payment_webhook_v2_enabled=True,
        yookassa_receipt_tax_system_code=1,
        yookassa_receipt_product_vat_code=1,
        yookassa_receipt_delivery_vat_code=1,
        yookassa_receipt_product_payment_mode="full_payment",
        yookassa_receipt_delivery_payment_mode="full_payment",
        yookassa_receipt_product_subject="non_marked",
        yookassa_receipt_delivery_subject="service",
    )


@dataclass
class FakeProvider:
    outcomes: list[ProviderPaymentSnapshot | Exception]
    calls: list[tuple[str, str, bytes | None]] = field(default_factory=list)

    async def capture_payment(
        self,
        provider_payment_id: str,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> ProviderPaymentSnapshot:
        self.calls.append(("capture", idempotence_key, request_body))
        return self._outcome()

    async def cancel_payment(
        self,
        provider_payment_id: str,
        *,
        idempotence_key: str,
    ) -> ProviderPaymentSnapshot:
        self.calls.append(("cancel", idempotence_key, None))
        return self._outcome()

    def _outcome(self) -> ProviderPaymentSnapshot:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@dataclass
class FakeLifecycle:
    calls: list[tuple[int, int]] = field(default_factory=list)

    async def confirm_payment(
        self,
        session,
        *,
        order_id: int,
        payment_attempt_id: int,
        now: datetime,
    ) -> Order:
        del now
        self.calls.append((order_id, payment_attempt_id))
        order = await session.get(Order, order_id)
        assert order is not None
        order.status = "processing"
        order.payment_status = "paid"
        order.version += 1
        await session.flush()
        return order


def _snapshot(order_id: int, *, status: str) -> ProviderPaymentSnapshot:
    values: dict[str, object] = {
        "provider_payment_id": PROVIDER_PAYMENT_ID,
        "status": status,
        "amount": "100.00",
        "currency": "RUB",
        "metadata_order_id": order_id,
        "payment_method": "bank_card" if status != "canceled" else None,
        "paid": status == "succeeded",
        "test": True,
        "provider_created_at": "2026-09-04T11:00:00Z",
    }
    if status == "succeeded":
        values["captured_at"] = "2026-09-04T12:00:00Z"
    if status == "canceled":
        values["cancellation_party"] = "merchant"
        values["cancellation_reason"] = "canceled_by_merchant"
    return ProviderPaymentSnapshot.model_validate(values)


async def _seed(database: DatabaseManager, *, capture_mode: str = "manual") -> tuple[int, int]:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        actor = User(
            email="admin@example.test",
            email_normalized="admin@example.test",
            status="active",
        )
        order = Order(
            email="customer@example.test",
            email_normalized="customer@example.test",
            phone="79000000000",
            first_name="Customer",
            delivery_city="Moscow",
            delivery_method="courier",
            delivery_address="Address",
            payment_method="card",
            items_subtotal=Decimal("100.00"),
            delivery_price=Decimal("0.00"),
            total_price=Decimal("100.00"),
            currency="RUB",
            status="new",
            payment_status="pending",
            version=1,
            request_fingerprint_sha256="f" * 64,
        )
        session.add_all([actor, order])
        await session.flush()
        payment = Payment(
            order_id=order.id,
            status="pending",
            amount=Decimal("100.00"),
            currency="RUB",
        )
        session.add(payment)
        await session.flush()
        attempt = PaymentAttempt(
            payment_id=payment.id,
            attempt_number=1,
            client_key_digest_sha256="a" * 64,
            provider_idempotence_key="00000000-0000-4000-8000-000000000001",
            request_fingerprint_sha256="b" * 64,
            payment_method="bank_card",
            capture_mode=capture_mode,
            status="waiting_for_capture",
            provider_payment_id=PROVIDER_PAYMENT_ID,
            provider_request_sha256="c" * 64,
            creation_started_at=NOW - timedelta(minutes=10),
            creation_last_attempt_at=NOW - timedelta(minutes=10),
            creation_attempts_count=1,
            provider_created_at=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(days=1),
        )
        session.add(attempt)
        await session.commit()
        return actor.id, attempt.id


def test_capture_is_durable_and_idempotent(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "capture.db"))
        await database.startup()
        try:
            actor_id, attempt_id = await _seed(database)
            provider = FakeProvider([_snapshot(1, status="succeeded")])
            lifecycle = FakeLifecycle()
            service = PaymentOperationService(
                database.settings,
                provider,
                payment_service=PaymentService(database.settings),
                order_lifecycle=lifecycle,
                provider_key_factory=lambda: PROVIDER_KEY,
            )
            async with database.session() as session:
                pending = await service.get_order_payment(session, order_id=1)
                result = await service.capture_order(
                    session,
                    order_id=1,
                    client_key="capture_operation_key_0001",
                    actor_user_id=actor_id,
                    now=NOW,
                )
            assert pending.capture_mode == "manual"
            assert pending.status == "waiting_for_capture"
            assert result.operation_status == "succeeded"
            assert result.payment_status == "succeeded"
            assert provider.calls == [("capture", PROVIDER_KEY, b"{}")]
            assert lifecycle.calls == [(1, attempt_id)]

            async with database.session() as session:
                replay = await service.capture_order(
                    session,
                    order_id=1,
                    client_key="capture_operation_key_0001",
                    actor_user_id=actor_id,
                    now=NOW + timedelta(minutes=1),
                )
                operation = await session.scalar(select(PaymentOperation))
                order = await session.get(Order, 1)
            assert replay.replayed
            assert operation is not None and operation.attempts_count == 1
            assert order is not None and order.payment_status == "paid"
            assert len(provider.calls) == 1
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cancel_resolves_hold_without_marking_order_paid(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "cancel.db"))
        await database.startup()
        try:
            actor_id, attempt_id = await _seed(database)
            provider = FakeProvider([_snapshot(1, status="canceled")])
            service = PaymentOperationService(
                database.settings,
                provider,
                provider_key_factory=lambda: PROVIDER_KEY,
            )
            async with database.session() as session:
                result = await service.cancel(
                    session,
                    attempt_id=attempt_id,
                    client_key="cancel_operation_key_0001",
                    actor_user_id=actor_id,
                    now=NOW + timedelta(days=2),
                )
            assert result.payment_status == "canceled"
            async with database.session() as session:
                order = await session.get(Order, 1)
            assert order is not None and order.payment_status == "pending"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_operation_retries_unknown_outcome_with_same_provider_key(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "unknown.db"))
        await database.startup()
        try:
            actor_id, attempt_id = await _seed(database)
            provider = FakeProvider(
                [
                    YooKassaProviderError("timeout", retryable=True, outcome_unknown=True),
                    _snapshot(1, status="succeeded"),
                ]
            )
            service = PaymentOperationService(
                database.settings,
                provider,
                order_lifecycle=FakeLifecycle(),
                provider_key_factory=lambda: PROVIDER_KEY,
            )
            async with database.session() as session:
                with pytest.raises(PaymentOperationFailedError) as first:
                    await service.capture(
                        session,
                        attempt_id=attempt_id,
                        client_key="capture_operation_key_0002",
                        actor_user_id=actor_id,
                        now=NOW,
                    )
            assert first.value.outcome_unknown
            async with database.session() as session:
                result = await service.capture(
                    session,
                    attempt_id=attempt_id,
                    client_key="capture_operation_key_0002",
                    actor_user_id=actor_id,
                    now=NOW + timedelta(seconds=61),
                )
                operation = await session.scalar(select(PaymentOperation))
            assert result.payment_status == "succeeded"
            assert operation is not None and operation.attempts_count == 2
            assert [call[1] for call in provider.calls] == [PROVIDER_KEY, PROVIDER_KEY]
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_operation_resolves_from_webhook_evidence_after_timeout(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "webhook-resolution.db"))
        await database.startup()
        try:
            actor_id, attempt_id = await _seed(database)
            provider = FakeProvider(
                [YooKassaProviderError("timeout", retryable=True, outcome_unknown=True)]
            )
            lifecycle = FakeLifecycle()
            service = PaymentOperationService(
                database.settings,
                provider,
                order_lifecycle=lifecycle,
                provider_key_factory=lambda: PROVIDER_KEY,
            )
            async with database.session() as session:
                with pytest.raises(PaymentOperationFailedError):
                    await service.capture(
                        session,
                        attempt_id=attempt_id,
                        client_key="capture_operation_key_0004",
                        actor_user_id=actor_id,
                        now=NOW,
                    )

            async with database.session() as session:
                await PaymentService(database.settings).record_provider_snapshot(
                    session,
                    attempt_id=attempt_id,
                    snapshot=_snapshot(1, status="succeeded"),
                    now=NOW + timedelta(seconds=20),
                )
                await session.commit()

            async with database.session() as session:
                result = await service.capture(
                    session,
                    attempt_id=attempt_id,
                    client_key="capture_operation_key_0004",
                    actor_user_id=actor_id,
                    now=NOW + timedelta(seconds=61),
                )
                operation = await session.scalar(select(PaymentOperation))
            assert result.replayed
            assert result.operation_status == "succeeded"
            assert operation is not None and operation.attempts_count == 1
            assert len(provider.calls) == 1
            assert lifecycle.calls == [(1, attempt_id)]
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_automatic_payment_cannot_be_manually_captured(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "automatic.db"))
        await database.startup()
        try:
            actor_id, attempt_id = await _seed(database, capture_mode="automatic")
            provider = FakeProvider([])
            service = PaymentOperationService(database.settings, provider)
            async with database.session() as session:
                with pytest.raises(PaymentOperationConflictError):
                    await service.capture(
                        session,
                        attempt_id=attempt_id,
                        client_key="capture_operation_key_0003",
                        actor_user_id=actor_id,
                        now=NOW,
                    )
            assert provider.calls == []
        finally:
            await database.shutdown()

    asyncio.run(scenario())
