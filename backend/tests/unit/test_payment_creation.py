from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.inventory.service import InventoryReservationStateError
from app.modules.orders.models import Order, OrderItem
from app.modules.payments.creation import (
    PaymentCreationFailedError,
    PaymentCreationInProgressError,
    PaymentCreationRequestConflictError,
    PaymentCreationRetryExpiredError,
    PaymentCreationService,
)
from app.modules.payments.models import (
    Payment,
    PaymentAttempt,
    PaymentReconciliationJob,
)
from app.modules.payments.provider import YooKassaProviderError
from app.modules.payments.reconciliation import PaymentReconciliationProcessor
from app.modules.payments.schemas import ProviderPaymentSnapshot
from app.modules.payments.service import PaymentService

PROVIDER_KEY_1 = "00000000-0000-4000-8000-000000000001"
PROVIDER_KEY_2 = "00000000-0000-4000-8000-000000000002"
PROVIDER_PAYMENT_ID = "2c111111-000f-5000-a000-111111111111"
NOW = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        public_base_url="https://shop.example.test",
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
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
    )


def _order() -> Order:
    return Order(
        email="Customer@Example.Test",
        email_normalized="customer@example.test",
        phone="+79000000000",
        first_name="Customer",
        delivery_city="Moscow",
        delivery_method="courier",
        delivery_address="Safe address",
        payment_method="card",
        items_subtotal=Decimal("100.00"),
        delivery_price=Decimal("25.50"),
        total_price=Decimal("125.50"),
        currency="RUB",
        status="new",
        payment_status="pending",
        version=1,
        request_fingerprint_sha256="f" * 64,
        items=[
            OrderItem(
                client_item_id="line-1",
                product_id_snapshot=10,
                variant_id_snapshot=20,
                sku_snapshot="SKU-10",
                title_snapshot="  Платье   летнее  ",
                unit_price=Decimal("50.00"),
                quantity=2,
                line_total=Decimal("100.00"),
                image_url_snapshot="https://cdn.example.test/item.webp",
                size_snapshot="M",
                color_snapshot="black",
                customization_snapshot=None,
                sort_order=0,
            )
        ],
    )


def _snapshot(order_id: int, *, status: str = "pending") -> ProviderPaymentSnapshot:
    values: dict[str, object] = {
        "provider_payment_id": PROVIDER_PAYMENT_ID,
        "status": status,
        "amount": "125.50",
        "currency": "RUB",
        "metadata_order_id": order_id,
        "payment_method": "bank_card",
        "paid": status in {"waiting_for_capture", "succeeded"},
        "test": True,
        "provider_created_at": "2026-08-11T12:00:00Z",
    }
    if status == "pending":
        values["confirmation_url"] = "https://yoomoney.ru/checkout/payment/1"
    if status == "succeeded":
        values["captured_at"] = "2026-08-11T12:01:00Z"
    return ProviderPaymentSnapshot.model_validate(values)


async def _create_schema(database: DatabaseManager) -> None:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _prepare(
    database: DatabaseManager,
    service: PaymentService,
    *,
    client_key: str,
    order_id: int,
) -> int:
    async with database.session() as session:
        prepared = await service.prepare_attempt(
            session,
            order_id=order_id,
            client_attempt_key=client_key,
        )
        await session.commit()
        return prepared.attempt_id


@dataclass
class FakeCreationProvider:
    outcomes: list[ProviderPaymentSnapshot | Exception]
    get_outcomes: list[ProviderPaymentSnapshot | Exception] = field(default_factory=list)
    calls: list[tuple[str, bytes]] = field(default_factory=list)
    get_calls: list[str] = field(default_factory=list)
    inspect_committed: object | None = None

    async def create_payment(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> ProviderPaymentSnapshot:
        self.calls.append((idempotence_key, request_body))
        if self.inspect_committed is not None:
            await self.inspect_committed()
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        self.get_calls.append(provider_payment_id)
        outcome = self.get_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@dataclass
class FakeOrderLifecycle:
    fail_once: bool = False
    calls: list[int] = field(default_factory=list)
    payment_attempt_ids: list[int] = field(default_factory=list)

    async def confirm_payment(
        self,
        session,
        *,
        order_id: int,
        payment_attempt_id: int,
        now: datetime,
    ) -> Order:
        del now
        self.calls.append(order_id)
        self.payment_attempt_ids.append(payment_attempt_id)
        if self.fail_once:
            self.fail_once = False
            raise InventoryReservationStateError("synthetic reservation failure")
        order = await session.get(Order, order_id)
        assert order is not None
        order.status = "processing"
        order.payment_status = "paid"
        order.version += 1
        await session.flush()
        return order


def test_creation_commits_before_network_and_builds_exact_receipt(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "create.db"))
        await database.startup()
        try:
            await _create_schema(database)
            async with database.session() as session:
                order = _order()
                session.add(order)
                await session.commit()
                order_id = order.id
            payment_service = PaymentService(
                database.settings,
                provider_key_factory=lambda: PROVIDER_KEY_1,
            )
            attempt_id = await _prepare(
                database,
                payment_service,
                client_key="payment_creation_client_key_0001",
                order_id=order_id,
            )

            async def inspect_committed() -> None:
                async with database.session() as observer:
                    attempt = await observer.get(PaymentAttempt, attempt_id)
                    assert attempt is not None
                    assert attempt.provider_request_sha256 is not None
                    assert attempt.creation_attempts_count == 1
                    assert attempt.creation_started_at is not None

            provider = FakeCreationProvider([_snapshot(order_id)])
            provider.inspect_committed = inspect_committed
            creator = PaymentCreationService(
                database.settings,
                provider,
                payment_service=payment_service,
            )
            async with database.session() as session:
                result = await creator.create_attempt(
                    session,
                    attempt_id=attempt_id,
                    now=NOW,
                )

            assert result.status == "pending"
            assert result.provider_payment_id == PROVIDER_PAYMENT_ID
            assert result.confirmation_url == "https://yoomoney.ru/checkout/payment/1"
            assert not result.replayed
            assert len(provider.calls) == 1
            idempotence_key, request_body = provider.calls[0]
            assert idempotence_key == PROVIDER_KEY_1
            payload = json.loads(request_body)
            assert payload["amount"] == {"currency": "RUB", "value": "125.50"}
            assert payload["capture"] is True
            assert payload["confirmation"]["return_url"] == (
                f"https://shop.example.test/order/{order_id}"
            )
            assert payload["metadata"] == {"order_id": order_id}
            assert payload["receipt"]["customer"] == {"email": "customer@example.test"}
            assert payload["receipt"]["tax_system_code"] == 1
            assert payload["receipt"]["items"] == [
                {
                    "amount": {"currency": "RUB", "value": "50.00"},
                    "description": "Платье летнее",
                    "payment_mode": "full_payment",
                    "payment_subject": "non_marked",
                    "quantity": "2",
                    "vat_code": 1,
                },
                {
                    "amount": {"currency": "RUB", "value": "25.50"},
                    "description": "Доставка",
                    "payment_mode": "full_payment",
                    "payment_subject": "service",
                    "quantity": "1.00",
                    "vat_code": 1,
                },
            ]
            async with database.session() as session:
                attempt = await creator.repository.get_attempt_for_update(
                    session,
                    attempt_id=attempt_id,
                )
                job = await session.scalar(
                    select(PaymentReconciliationJob).where(
                        PaymentReconciliationJob.payment_attempt_id == attempt_id
                    )
                )
                assert attempt is not None
                assert attempt.provider_request_sha256 == hashlib.sha256(request_body).hexdigest()
                assert attempt.creation_attempts_count == 1
                assert job is not None and job.status == "scheduled"
                persisted = repr(attempt.__dict__)
                assert "customer@example.test" not in persisted
                assert "Платье летнее" not in persisted
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_unknown_creation_retries_the_exact_key_and_body(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "unknown.db"))
        await database.startup()
        try:
            await _create_schema(database)
            async with database.session() as session:
                order = _order()
                session.add(order)
                await session.commit()
                order_id = order.id
            payment_service = PaymentService(
                database.settings,
                provider_key_factory=lambda: PROVIDER_KEY_1,
            )
            attempt_id = await _prepare(
                database,
                payment_service,
                client_key="payment_creation_client_key_0002",
                order_id=order_id,
            )
            provider = FakeCreationProvider(
                [
                    YooKassaProviderError(
                        "timeout",
                        retryable=True,
                        outcome_unknown=True,
                    ),
                    _snapshot(order_id),
                ]
            )
            creator = PaymentCreationService(
                database.settings,
                provider,
                payment_service=payment_service,
            )
            with pytest.raises(PaymentCreationFailedError) as first_failure:
                async with database.session() as session:
                    await creator.create_attempt(session, attempt_id=attempt_id, now=NOW)
            assert first_failure.value.code == "timeout"
            assert first_failure.value.outcome_unknown
            async with database.session() as session:
                attempt = await creator.repository.get_attempt_for_update(
                    session,
                    attempt_id=attempt_id,
                )
                assert attempt is not None and attempt.status == "unknown"

            async with database.session() as session:
                retried = await creator.create_attempt(
                    session,
                    attempt_id=attempt_id,
                    now=NOW + timedelta(seconds=1),
                )
            assert retried.status == "pending"
            assert len(provider.calls) == 2
            assert provider.calls[0] == provider.calls[1]
            async with database.session() as session:
                attempt = await session.get(PaymentAttempt, attempt_id)
                assert attempt is not None and attempt.creation_attempts_count == 2
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_immediate_success_is_atomic_with_order_and_can_retry_local_failure(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "immediate-success.db"))
        await database.startup()
        try:
            await _create_schema(database)
            async with database.session() as session:
                order = _order()
                session.add(order)
                await session.commit()
                order_id = order.id
            payment_service = PaymentService(
                database.settings,
                provider_key_factory=lambda: PROVIDER_KEY_1,
            )
            attempt_id = await _prepare(
                database,
                payment_service,
                client_key="payment_creation_client_key_success",
                order_id=order_id,
            )
            provider = FakeCreationProvider(
                [_snapshot(order_id, status="succeeded")],
                get_outcomes=[_snapshot(order_id, status="succeeded")],
            )
            lifecycle = FakeOrderLifecycle(fail_once=True)
            creator = PaymentCreationService(
                database.settings,
                provider,
                payment_service=payment_service,
                order_lifecycle=lifecycle,
            )

            with pytest.raises(PaymentCreationFailedError) as local_failure:
                async with database.session() as session:
                    await creator.create_attempt(session, attempt_id=attempt_id, now=NOW)
            assert local_failure.value.code == "paid_order_transition_failed"
            assert local_failure.value.outcome_unknown
            async with database.session() as session:
                attempt = await session.get(PaymentAttempt, attempt_id)
                payment = await session.scalar(select(Payment))
                order = await session.get(Order, order_id)
                assert attempt is not None and attempt.status == "unknown"
                assert attempt.provider_payment_id == PROVIDER_PAYMENT_ID
                assert payment is not None and payment.status == "pending"
                assert order is not None and order.payment_status == "pending"
                job = await session.scalar(select(PaymentReconciliationJob))
                assert job is not None and job.status == "scheduled"

            async with database.session() as session:
                unknown = await creator.create_attempt(
                    session,
                    attempt_id=attempt_id,
                    now=NOW + timedelta(seconds=1),
                )
            assert unknown.status == "unknown" and unknown.replayed
            assert len(provider.calls) == 1

            reconciler = PaymentReconciliationProcessor(
                database.settings,
                provider,
                payment_service=payment_service,
                order_lifecycle=lifecycle,
            )
            async with database.session() as session:
                reconciliation = await reconciler.process_once(
                    session,
                    worker_id="creation-recovery-worker",
                    now=NOW
                    + timedelta(
                        seconds=database.settings.payment_reconciliation_interval_seconds + 1
                    ),
                )
            assert reconciliation is not None and reconciliation.status == "completed"
            assert provider.get_calls == [PROVIDER_PAYMENT_ID]
            assert lifecycle.calls == [order_id, order_id]
            assert lifecycle.payment_attempt_ids == [attempt_id, attempt_id]

            async with database.session() as session:
                result = await creator.create_attempt(
                    session,
                    attempt_id=attempt_id,
                    now=NOW
                    + timedelta(
                        seconds=database.settings.payment_reconciliation_interval_seconds + 2
                    ),
                )
            assert result.status == "succeeded" and result.replayed
            assert lifecycle.calls == [order_id, order_id, order_id]
            assert lifecycle.payment_attempt_ids == [attempt_id, attempt_id, attempt_id]
            async with database.session() as session:
                attempt = await session.get(PaymentAttempt, attempt_id)
                payment = await session.scalar(select(Payment))
                order = await session.get(Order, order_id)
                job = await session.scalar(select(PaymentReconciliationJob))
                assert attempt is not None and attempt.status == "succeeded"
                assert payment is not None and payment.status == "succeeded"
                assert order is not None and order.payment_status == "paid"
                assert order.status == "processing"
                assert job is not None and job.status == "completed"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_known_rejection_closes_attempt_and_allows_new_client_key(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "rejected.db"))
        await database.startup()
        try:
            await _create_schema(database)
            async with database.session() as session:
                order = _order()
                session.add(order)
                await session.commit()
                order_id = order.id
            keys = iter((PROVIDER_KEY_1, PROVIDER_KEY_2))
            payment_service = PaymentService(
                database.settings,
                provider_key_factory=lambda: next(keys),
            )
            attempt_id = await _prepare(
                database,
                payment_service,
                client_key="payment_creation_client_key_0003",
                order_id=order_id,
            )
            provider = FakeCreationProvider(
                [YooKassaProviderError("request_rejected", retryable=False)]
            )
            creator = PaymentCreationService(
                database.settings,
                provider,
                payment_service=payment_service,
            )
            with pytest.raises(PaymentCreationFailedError) as failure:
                async with database.session() as session:
                    await creator.create_attempt(session, attempt_id=attempt_id, now=NOW)
            assert not failure.value.outcome_unknown
            async with database.session() as session:
                failed = await session.get(PaymentAttempt, attempt_id)
                assert failed is not None and failed.status == "failed"
                assert failed.resolved_at is not None
                assert failed.provider_payment_id is None

            second_id = await _prepare(
                database,
                payment_service,
                client_key="payment_creation_client_key_0004",
                order_id=order_id,
            )
            async with database.session() as session:
                second = await session.get(PaymentAttempt, second_id)
                assert second is not None and second.attempt_number == 2
                assert second.provider_idempotence_key == PROVIDER_KEY_2
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_creation_blocks_fresh_duplicate_and_changed_request(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "guards.db"))
        await database.startup()
        try:
            await _create_schema(database)
            async with database.session() as session:
                order = _order()
                session.add(order)
                await session.commit()
                order_id = order.id
            payment_service = PaymentService(
                database.settings,
                provider_key_factory=lambda: PROVIDER_KEY_1,
            )
            attempt_id = await _prepare(
                database,
                payment_service,
                client_key="payment_creation_client_key_0005",
                order_id=order_id,
            )
            provider = FakeCreationProvider([])
            creator = PaymentCreationService(
                database.settings,
                provider,
                payment_service=payment_service,
            )
            async with database.session() as session:
                attempt = await creator.repository.get_attempt_for_update(
                    session,
                    attempt_id=attempt_id,
                )
                assert attempt is not None
                order = await creator.repository.get_order_with_items_for_update(
                    session,
                    order_id=order_id,
                )
                assert order is not None
                digest = hashlib.sha256(
                    creator.build_request(order=order, attempt=attempt).canonical_bytes()
                ).hexdigest()
                attempt.provider_request_sha256 = digest
                attempt.creation_started_at = NOW
                attempt.creation_last_attempt_at = NOW
                attempt.creation_attempts_count = 1
                await session.commit()

            with pytest.raises(PaymentCreationInProgressError):
                async with database.session() as session:
                    await creator.create_attempt(
                        session,
                        attempt_id=attempt_id,
                        now=NOW + timedelta(seconds=1),
                    )
            assert provider.calls == []

            changed_settings = _settings(tmp_path / "guards.db").model_copy(
                update={"public_base_url": "https://changed.example.test"}
            )
            changed_creator = PaymentCreationService(
                changed_settings,
                provider,
                payment_service=payment_service,
            )
            with pytest.raises(PaymentCreationRequestConflictError):
                async with database.session() as session:
                    await changed_creator.create_attempt(
                        session,
                        attempt_id=attempt_id,
                        now=NOW + timedelta(minutes=2),
                    )
            assert provider.calls == []
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_expired_idempotence_window_fails_closed_without_network(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "expired.db"))
        await database.startup()
        try:
            await _create_schema(database)
            async with database.session() as session:
                order = _order()
                session.add(order)
                await session.commit()
                order_id = order.id
            payment_service = PaymentService(
                database.settings,
                provider_key_factory=lambda: PROVIDER_KEY_1,
            )
            attempt_id = await _prepare(
                database,
                payment_service,
                client_key="payment_creation_client_key_0006",
                order_id=order_id,
            )
            provider = FakeCreationProvider([])
            creator = PaymentCreationService(
                database.settings,
                provider,
                payment_service=payment_service,
            )
            async with database.session() as session:
                attempt = await creator.repository.get_attempt_for_update(
                    session,
                    attempt_id=attempt_id,
                )
                assert attempt is not None
                order = await creator.repository.get_order_with_items_for_update(
                    session,
                    order_id=order_id,
                )
                assert order is not None
                attempt.provider_request_sha256 = hashlib.sha256(
                    creator.build_request(order=order, attempt=attempt).canonical_bytes()
                ).hexdigest()
                attempt.creation_started_at = NOW
                attempt.creation_last_attempt_at = NOW
                attempt.creation_attempts_count = 1
                await session.commit()

            expired_at = NOW + timedelta(
                seconds=database.settings.payment_creation_retry_window_seconds + 1
            )
            with pytest.raises(PaymentCreationRetryExpiredError):
                async with database.session() as session:
                    await creator.create_attempt(
                        session,
                        attempt_id=attempt_id,
                        now=expired_at,
                    )
            assert provider.calls == []
            async with database.session() as session:
                attempt = await session.get(PaymentAttempt, attempt_id)
                assert attempt is not None and attempt.status == "failed"
                assert attempt.last_error_code == "idempotence_window_expired"
        finally:
            await database.shutdown()

    asyncio.run(scenario())
