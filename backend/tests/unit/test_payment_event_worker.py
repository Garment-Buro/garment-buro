from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product
from app.modules.fulfillment.models import FulfillmentJob
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import Order, OrderStatusHistory
from app.modules.orders.schemas import OrderCreationCommand
from app.modules.orders.service import OrderCreationService, OrderLifecycleService
from app.modules.payments.models import (
    Payment,
    PaymentAttempt,
    PaymentEvent,
    PaymentReconciliationJob,
)
from app.modules.payments.provider import YooKassaProviderError
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import ProviderPaymentSnapshot
from app.modules.payments.service import PaymentService
from app.modules.payments.worker import PaymentEventProcessor

PROVIDER_PAYMENT_ID = "2c111111-000f-5000-a000-111111111111"
PROVIDER_KEY = "00000000-0000-4000-8000-000000000001"


def _settings(path: Path, *, fulfillment_enabled: bool = False) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        payment_event_retry_base_seconds=30,
        payment_event_retry_cap_seconds=300,
        payment_event_processing_timeout_seconds=300,
        fulfillment_outbox_enabled=fulfillment_enabled,
    )


def _snapshot(
    order_id: int,
    *,
    status: str,
    amount: str = "100.00",
) -> ProviderPaymentSnapshot:
    values: dict[str, object] = {
        "provider_payment_id": PROVIDER_PAYMENT_ID,
        "status": status,
        "amount": amount,
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
    if status == "canceled":
        values["cancellation_party"] = "yoo_money"
        values["cancellation_reason"] = "payment_expired"
    return ProviderPaymentSnapshot.model_validate(values)


def _webhook_body(snapshot: ProviderPaymentSnapshot) -> bytes:
    payload: dict[str, object] = {
        "type": "notification",
        "event": f"payment.{snapshot.status}",
        "object": {
            "id": snapshot.provider_payment_id,
            "status": snapshot.status,
            "amount": {"value": str(snapshot.amount), "currency": snapshot.currency},
            "metadata": {"order_id": str(snapshot.metadata_order_id)},
            "payment_method": {"type": snapshot.payment_method},
            "paid": snapshot.paid,
            "test": snapshot.test,
            "created_at": snapshot.provider_created_at.isoformat(),
        },
    }
    payment = payload["object"]
    assert isinstance(payment, dict)
    if snapshot.captured_at is not None:
        payment["captured_at"] = snapshot.captured_at.isoformat()
    if snapshot.cancellation_party is not None:
        payment["cancellation_details"] = {
            "party": snapshot.cancellation_party,
            "reason": snapshot.cancellation_reason,
        }
    return json.dumps(payload).encode()


async def _seed_event(
    database: DatabaseManager,
    *,
    event_status: str,
    created_at: datetime,
) -> tuple[int, int, int, int]:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        product = Product(
            title="Server product",
            price=Decimal("100.00"),
            is_active=True,
            stock_quantity=3,
            sizes=["M"],
            colors=["black"],
        )
        session.add(product)
        await session.flush()
        created = await OrderCreationService(database.settings).create(
            session,
            idempotency_key="worker_order_attempt_0001",
            command=OrderCreationCommand.model_validate(
                {
                    "email": "customer@example.test",
                    "phone": "+79000000000",
                    "first_name": "Customer",
                    "delivery_city": "Moscow",
                    "delivery_method": "pickup",
                    "delivery_address": "Showroom",
                    "payment_method": "card",
                    "items": [
                        {
                            "id": "worker-line-1",
                            "product_id": product.id,
                            "title": "Ignored",
                            "price": "1.00",
                            "size": "M",
                            "color": "black",
                            "quantity": 1,
                        }
                    ],
                    "claimed_total_price": "100.00",
                    "delivery_price": "0.00",
                }
            ),
            now=created_at,
        )
        payment_service = PaymentService(
            database.settings,
            provider_key_factory=lambda: PROVIDER_KEY,
        )
        prepared = await payment_service.prepare_attempt(
            session,
            order_id=created.order_id,
            client_attempt_key="worker_payment_attempt_0001",
        )
        await payment_service.record_provider_snapshot(
            session,
            attempt_id=prepared.attempt_id,
            snapshot=_snapshot(created.order_id, status="pending"),
            now=created_at,
        )
        event_snapshot = _snapshot(created.order_id, status=event_status)
        received = await payment_service.intake_event(
            session,
            raw_body=_webhook_body(event_snapshot),
            source_ip="185.71.76.1",
            now=created_at,
        )
        await session.commit()
        return created.order_id, product.id, prepared.attempt_id, received.event_id


class InspectingProvider:
    def __init__(
        self,
        database: DatabaseManager,
        event_id: int,
        snapshot: ProviderPaymentSnapshot,
        *,
        expected_attempts: int,
        expected_worker: str,
    ) -> None:
        self.database = database
        self.event_id = event_id
        self.snapshot = snapshot
        self.expected_attempts = expected_attempts
        self.expected_worker = expected_worker
        self.observed_committed_claim = False

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        assert provider_payment_id == PROVIDER_PAYMENT_ID
        async with self.database.session() as session:
            event = await session.get(PaymentEvent, self.event_id)
            assert event is not None
            assert event.status == "processing"
            assert event.attempts_count == self.expected_attempts
            assert event.locked_by == self.expected_worker
            self.observed_committed_claim = True
        return self.snapshot


class SequenceProvider:
    def __init__(self, outcomes: list[ProviderPaymentSnapshot | Exception]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        assert provider_payment_id == PROVIDER_PAYMENT_ID
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RecordingLifecycle:
    def __init__(self, settings: Settings) -> None:
        self.delegate = OrderLifecycleService(settings)
        self.calls: list[tuple[int, int]] = []

    async def confirm_payment(
        self,
        session,
        *,
        order_id: int,
        payment_attempt_id: int,
        now: datetime,
    ) -> Order:
        self.calls.append((order_id, payment_attempt_id))
        return await self.delegate.confirm_payment(
            session,
            order_id=order_id,
            payment_attempt_id=payment_attempt_id,
            now=now,
        )


def test_worker_commits_claim_then_atomically_confirms_payment_and_inventory(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "success.db", fulfillment_enabled=True)
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, product_id, attempt_id, event_id = await _seed_event(
                database,
                event_status="succeeded",
                created_at=created_at,
            )
            crash_time = created_at + timedelta(seconds=10)
            async with database.session() as session:
                abandoned = await PaymentRepository().claim_next_event(
                    session,
                    now=crash_time,
                    stale_before=crash_time - timedelta(minutes=5),
                    worker_id="crashed-worker",
                )
                assert abandoned is not None
                await session.commit()

            worker_time = crash_time + timedelta(seconds=301)
            provider = InspectingProvider(
                database,
                event_id,
                _snapshot(order_id, status="succeeded"),
                expected_attempts=2,
                expected_worker="worker-2",
            )
            lifecycle = RecordingLifecycle(settings)
            processor = PaymentEventProcessor(
                settings,
                provider,
                order_lifecycle=lifecycle,
            )
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="worker-2",
                    now=worker_time,
                )
            assert result is not None and result.status == "processed"
            assert result.attempt_number == 2 and result.error_code is None
            assert provider.observed_committed_claim
            assert lifecycle.calls == [(order_id, attempt_id)]

            async with database.session() as session:
                event = await session.get(PaymentEvent, event_id)
                reconciliation = await session.scalar(select(PaymentReconciliationJob))
                payment = await session.scalar(select(Payment))
                attempt = await session.get(PaymentAttempt, attempt_id)
                order = await session.get(Order, order_id)
                product = await session.get(Product, product_id)
                reservation = await session.scalar(select(InventoryReservation))
                history_count = int(
                    await session.scalar(select(func.count()).select_from(OrderStatusHistory)) or 0
                )
                fulfillment_jobs = list(
                    await session.scalars(select(FulfillmentJob).order_by(FulfillmentJob.kind))
                )
                assert event is not None and event.status == "processed"
                assert reconciliation is not None and reconciliation.status == "completed"
                assert event.processed_at == worker_time.replace(tzinfo=None)
                assert event.locked_at is None and event.locked_by is None
                assert payment is not None and payment.status == "succeeded"
                assert attempt is not None and attempt.status == "succeeded"
                assert order is not None and order.status == "processing"
                assert order.payment_status == "paid" and order.version == 2
                assert product is not None and product.stock_quantity == 2
                assert product.reserved_quantity == 0
                assert reservation is not None and reservation.status == "confirmed"
                assert history_count == 2
                assert {job.kind for job in fulfillment_jobs} == {
                    "crm_order_project",
                    "customer_payment_email",
                }
                assert {job.source_payment_attempt_id for job in fulfillment_jobs} == {attempt_id}

            async with database.session() as session:
                assert (
                    await processor.process_once(
                        session,
                        worker_id="worker-2",
                        now=worker_time,
                    )
                    is None
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_worker_retries_provider_failures_with_bounded_backoff(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "retry.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, _, _, event_id = await _seed_event(
                database,
                event_status="succeeded",
                created_at=created_at,
            )
            provider = SequenceProvider(
                [
                    YooKassaProviderError("rate_limited", retryable=True),
                    _snapshot(order_id, status="succeeded"),
                ]
            )
            processor = PaymentEventProcessor(settings, provider)
            first_time = created_at + timedelta(seconds=10)
            async with database.session() as session:
                first = await processor.process_once(
                    session,
                    worker_id="retry-worker",
                    now=first_time,
                )
            assert first is not None and first.status == "retry"
            assert first.error_code == "rate_limited" and first.attempt_number == 1
            async with database.session() as session:
                event = await session.get(PaymentEvent, event_id)
                assert event is not None
                assert event.available_at == (first_time + timedelta(seconds=30)).replace(
                    tzinfo=None
                )

            async with database.session() as session:
                assert (
                    await processor.process_once(
                        session,
                        worker_id="retry-worker",
                        now=first_time + timedelta(seconds=29),
                    )
                    is None
                )
            async with database.session() as session:
                second = await processor.process_once(
                    session,
                    worker_id="retry-worker",
                    now=first_time + timedelta(seconds=31),
                )
            assert second is not None and second.status == "processed"
            assert second.attempt_number == 2 and provider.calls == 2
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_worker_records_cancellation_without_canceling_retryable_order(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "canceled.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, product_id, attempt_id, event_id = await _seed_event(
                database,
                event_status="canceled",
                created_at=created_at,
            )
            processor = PaymentEventProcessor(
                settings,
                SequenceProvider([_snapshot(order_id, status="canceled")]),
            )
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="cancel-worker",
                    now=created_at + timedelta(seconds=10),
                )
            assert result is not None and result.status == "processed"

            async with database.session() as session:
                event = await session.get(PaymentEvent, event_id)
                payment = await session.scalar(select(Payment))
                attempt = await session.get(PaymentAttempt, attempt_id)
                order = await session.get(Order, order_id)
                product = await session.get(Product, product_id)
                reservation = await session.scalar(select(InventoryReservation))
                assert event is not None and event.status == "processed"
                assert payment is not None and payment.status == "canceled"
                assert attempt is not None and attempt.status == "canceled"
                assert order is not None and order.status == "new"
                assert order.payment_status == "pending" and order.version == 1
                assert product is not None and product.stock_quantity == 3
                assert product.reserved_quantity == 1
                assert reservation is not None and reservation.status == "active"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_worker_rejects_changed_provider_evidence_without_mutating_order(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "mismatch.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, _, attempt_id, event_id = await _seed_event(
                database,
                event_status="succeeded",
                created_at=created_at,
            )
            processor = PaymentEventProcessor(
                settings,
                SequenceProvider([_snapshot(order_id, status="succeeded", amount="100.01")]),
            )
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="mismatch-worker",
                    now=created_at + timedelta(seconds=10),
                )
            assert result is not None and result.status == "rejected"
            assert result.error_code == "provider_evidence_mismatch"

            async with database.session() as session:
                event = await session.get(PaymentEvent, event_id)
                payment = await session.scalar(select(Payment))
                attempt = await session.get(PaymentAttempt, attempt_id)
                order = await session.get(Order, order_id)
                assert event is not None and event.status == "rejected"
                assert payment is not None and payment.status == "pending"
                assert attempt is not None and attempt.status == "pending"
                assert order is not None and order.status == "new"
                assert order.payment_status == "pending"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_paid_event_becomes_dead_when_inventory_can_no_longer_confirm(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "expired.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, _, attempt_id, event_id = await _seed_event(
                database,
                event_status="succeeded",
                created_at=created_at,
            )
            processor = PaymentEventProcessor(
                settings,
                SequenceProvider([_snapshot(order_id, status="succeeded")]),
            )
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="expired-worker",
                    now=created_at + timedelta(seconds=1_801),
                )
            assert result is not None and result.status == "dead"
            assert result.error_code == "paid_order_transition_failed"

            async with database.session() as session:
                event = await session.get(PaymentEvent, event_id)
                payment = await session.scalar(select(Payment))
                attempt = await session.get(PaymentAttempt, attempt_id)
                order = await session.get(Order, order_id)
                assert event is not None and event.status == "dead"
                assert payment is not None and payment.status == "pending"
                assert attempt is not None and attempt.status == "pending"
                assert order is not None and order.payment_status == "pending"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_stale_last_attempt_is_finalized_without_another_provider_call(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "stale-exhausted.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            _, _, _, event_id = await _seed_event(
                database,
                event_status="succeeded",
                created_at=created_at,
            )
            async with database.session() as session:
                event = await session.get(PaymentEvent, event_id)
                assert event is not None
                event.max_attempts = 1
                await session.commit()

            crash_time = created_at + timedelta(seconds=10)
            async with database.session() as session:
                claimed = await PaymentRepository().claim_next_event(
                    session,
                    now=crash_time,
                    stale_before=crash_time - timedelta(minutes=5),
                    worker_id="last-attempt-worker",
                )
                assert claimed is not None and claimed.attempts_count == 1
                await session.commit()

            provider = SequenceProvider([_snapshot(1, status="succeeded")])
            processor = PaymentEventProcessor(settings, provider)
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="reaper-worker",
                    now=crash_time + timedelta(seconds=301),
                )
            assert result is not None and result.status == "dead"
            assert result.error_code == "worker_stale_exhausted"
            assert result.attempt_number == 1 and provider.calls == 0

            async with database.session() as session:
                event = await session.get(PaymentEvent, event_id)
                assert event is not None and event.status == "dead"
                assert event.locked_at is None and event.locked_by is None
        finally:
            await database.shutdown()

    asyncio.run(scenario())
