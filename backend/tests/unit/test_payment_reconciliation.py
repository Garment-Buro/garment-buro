from __future__ import annotations

import asyncio
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
from app.modules.payments.reconciliation import PaymentReconciliationProcessor
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import ProviderPaymentSnapshot
from app.modules.payments.service import PaymentService

PROVIDER_PAYMENT_ID = "2c111111-000f-5000-a000-111111111111"
PROVIDER_KEY = "00000000-0000-4000-8000-000000000001"


def _settings(path: Path, *, fulfillment_enabled: bool = False) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        payment_reconciliation_max_attempts=4,
        payment_reconciliation_interval_seconds=300,
        payment_reconciliation_retry_base_seconds=30,
        payment_reconciliation_retry_cap_seconds=300,
        payment_reconciliation_processing_timeout_seconds=300,
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


async def _seed_active_attempt(
    database: DatabaseManager,
    *,
    created_at: datetime,
) -> tuple[int, int, int, int]:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        product = Product(
            title="Reconciliation product",
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
            idempotency_key="reconciliation_order_0001",
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
                            "id": "reconciliation-line-1",
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
            client_attempt_key="reconciliation_payment_0001",
        )
        await payment_service.record_provider_snapshot(
            session,
            attempt_id=prepared.attempt_id,
            snapshot=_snapshot(created.order_id, status="pending"),
            now=created_at,
        )
        job = await session.scalar(select(PaymentReconciliationJob))
        assert job is not None
        await session.commit()
        return created.order_id, product.id, prepared.attempt_id, job.id


class InspectingProvider:
    def __init__(
        self,
        database: DatabaseManager,
        job_id: int,
        snapshot: ProviderPaymentSnapshot,
        *,
        expected_attempts: int,
        expected_worker: str,
    ) -> None:
        self.database = database
        self.job_id = job_id
        self.snapshot = snapshot
        self.expected_attempts = expected_attempts
        self.expected_worker = expected_worker
        self.observed_committed_claim = False

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        assert provider_payment_id == PROVIDER_PAYMENT_ID
        async with self.database.session() as session:
            job = await session.get(PaymentReconciliationJob, self.job_id)
            assert job is not None and job.status == "processing"
            assert job.attempts_count == self.expected_attempts
            assert job.locked_by == self.expected_worker
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


class ConcurrentTerminalProvider:
    def __init__(
        self,
        database: DatabaseManager,
        *,
        attempt_id: int,
        order_id: int,
        snapshot: ProviderPaymentSnapshot,
        now: datetime,
    ) -> None:
        self.database = database
        self.attempt_id = attempt_id
        self.order_id = order_id
        self.snapshot = snapshot
        self.now = now
        self.calls = 0

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        assert provider_payment_id == PROVIDER_PAYMENT_ID
        self.calls += 1
        async with self.database.session() as session:
            await PaymentService(self.database.settings).record_provider_snapshot(
                session,
                attempt_id=self.attempt_id,
                snapshot=self.snapshot,
                now=self.now,
            )
            await OrderLifecycleService(self.database.settings).confirm_payment(
                session,
                order_id=self.order_id,
                now=self.now,
            )
            await session.commit()
        return self.snapshot


def test_reconciliation_claims_before_get_and_atomically_confirms_order(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "success.db", fulfillment_enabled=True)
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, product_id, attempt_id, job_id = await _seed_active_attempt(
                database,
                created_at=created_at,
            )
            due_at = created_at + timedelta(seconds=301)
            provider = InspectingProvider(
                database,
                job_id,
                _snapshot(order_id, status="succeeded"),
                expected_attempts=1,
                expected_worker="reconciler-1",
            )
            lifecycle = RecordingLifecycle(settings)
            processor = PaymentReconciliationProcessor(
                settings,
                provider,
                order_lifecycle=lifecycle,
            )
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="reconciler-1",
                    now=due_at,
                )
            assert result is not None and result.status == "completed"
            assert result.observed_status == "succeeded" and result.error_code is None
            assert provider.observed_committed_claim
            assert lifecycle.calls == [(order_id, attempt_id)]

            async with database.session() as session:
                job = await session.get(PaymentReconciliationJob, job_id)
                attempt = await session.get(PaymentAttempt, attempt_id)
                payment = await session.scalar(select(Payment))
                order = await session.get(Order, order_id)
                product = await session.get(Product, product_id)
                reservation = await session.scalar(select(InventoryReservation))
                history_count = int(
                    await session.scalar(select(func.count()).select_from(OrderStatusHistory)) or 0
                )
                event_count = int(
                    await session.scalar(select(func.count()).select_from(PaymentEvent)) or 0
                )
                fulfillment_jobs = list(
                    await session.scalars(select(FulfillmentJob).order_by(FulfillmentJob.kind))
                )
                assert job is not None and job.status == "completed"
                assert job.completed_at == due_at.replace(tzinfo=None)
                assert job.last_checked_at == due_at.replace(tzinfo=None)
                assert job.last_observed_status == "succeeded"
                assert job.last_observation_sha256 is not None
                assert len(job.last_observation_sha256) == 64
                assert attempt is not None and attempt.status == "succeeded"
                assert payment is not None and payment.status == "succeeded"
                assert order is not None and order.status == "processing"
                assert order.payment_status == "paid"
                assert product is not None and product.stock_quantity == 2
                assert product.reserved_quantity == 0
                assert reservation is not None and reservation.status == "confirmed"
                assert history_count == 2
                assert event_count == 0
                assert {job.kind for job in fulfillment_jobs} == {
                    "crm_order_project",
                    "customer_payment_email",
                }
                assert {job.source_payment_attempt_id for job in fulfillment_jobs} == {attempt_id}
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_reconciliation_reschedules_active_state_then_completes(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "active.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, _, _, job_id = await _seed_active_attempt(
                database,
                created_at=created_at,
            )
            provider = SequenceProvider(
                [
                    _snapshot(order_id, status="pending"),
                    _snapshot(order_id, status="succeeded"),
                ]
            )
            processor = PaymentReconciliationProcessor(settings, provider)
            first_time = created_at + timedelta(seconds=301)
            async with database.session() as session:
                first = await processor.process_once(
                    session,
                    worker_id="active-worker",
                    now=first_time,
                )
            assert first is not None and first.status == "scheduled"
            assert first.observed_status == "pending" and first.error_code is None
            async with database.session() as session:
                job = await session.get(PaymentReconciliationJob, job_id)
                assert job is not None
                assert job.available_at == (first_time + timedelta(seconds=300)).replace(
                    tzinfo=None
                )

            async with database.session() as session:
                assert (
                    await processor.process_once(
                        session,
                        worker_id="active-worker",
                        now=first_time + timedelta(seconds=299),
                    )
                    is None
                )
            async with database.session() as session:
                second = await processor.process_once(
                    session,
                    worker_id="active-worker",
                    now=first_time + timedelta(seconds=301),
                )
            assert second is not None and second.status == "completed"
            assert second.attempt_number == 2 and provider.calls == 2
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_reconciliation_accepts_concurrent_terminal_webhook_completion(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "concurrent-webhook.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, product_id, attempt_id, job_id = await _seed_active_attempt(
                database,
                created_at=created_at,
            )
            due_at = created_at + timedelta(seconds=301)
            snapshot = _snapshot(order_id, status="succeeded")
            provider = ConcurrentTerminalProvider(
                database,
                attempt_id=attempt_id,
                order_id=order_id,
                snapshot=snapshot,
                now=due_at,
            )
            processor = PaymentReconciliationProcessor(settings, provider)
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="concurrent-worker",
                    now=due_at,
                )
            assert result is not None and result.status == "completed"
            assert result.attempt_number == 1 and provider.calls == 1

            async with database.session() as session:
                job = await session.get(PaymentReconciliationJob, job_id)
                order = await session.get(Order, order_id)
                product = await session.get(Product, product_id)
                history_count = int(
                    await session.scalar(select(func.count()).select_from(OrderStatusHistory)) or 0
                )
                assert job is not None and job.status == "completed"
                assert order is not None and order.payment_status == "paid"
                assert product is not None and product.stock_quantity == 2
                assert history_count == 2
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_reconciliation_retries_provider_failure_and_preserves_canceled_order(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "retry-cancel.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, product_id, attempt_id, job_id = await _seed_active_attempt(
                database,
                created_at=created_at,
            )
            provider = SequenceProvider(
                [
                    YooKassaProviderError("rate_limited", retryable=True),
                    _snapshot(order_id, status="canceled"),
                ]
            )
            processor = PaymentReconciliationProcessor(settings, provider)
            first_time = created_at + timedelta(seconds=301)
            async with database.session() as session:
                first = await processor.process_once(
                    session,
                    worker_id="retry-worker",
                    now=first_time,
                )
            assert first is not None and first.status == "retry"
            assert first.error_code == "rate_limited"
            async with database.session() as session:
                second = await processor.process_once(
                    session,
                    worker_id="retry-worker",
                    now=first_time + timedelta(seconds=31),
                )
            assert second is not None and second.status == "completed"
            assert second.observed_status == "canceled"

            async with database.session() as session:
                job = await session.get(PaymentReconciliationJob, job_id)
                attempt = await session.get(PaymentAttempt, attempt_id)
                payment = await session.scalar(select(Payment))
                order = await session.get(Order, order_id)
                product = await session.get(Product, product_id)
                reservation = await session.scalar(select(InventoryReservation))
                assert job is not None and job.status == "completed"
                assert attempt is not None and attempt.status == "canceled"
                assert payment is not None and payment.status == "canceled"
                assert order is not None and order.status == "new"
                assert order.payment_status == "pending"
                assert product is not None and product.reserved_quantity == 1
                assert reservation is not None and reservation.status == "active"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_reconciliation_rejects_changed_evidence_without_mutating_payment(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "mismatch.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, product_id, attempt_id, job_id = await _seed_active_attempt(
                database,
                created_at=created_at,
            )
            provider = SequenceProvider([_snapshot(order_id, status="succeeded", amount="101.00")])
            processor = PaymentReconciliationProcessor(settings, provider)
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="mismatch-worker",
                    now=created_at + timedelta(seconds=301),
                )
            assert result is not None and result.status == "dead"
            assert result.error_code == "provider_evidence_mismatch"

            async with database.session() as session:
                job = await session.get(PaymentReconciliationJob, job_id)
                attempt = await session.get(PaymentAttempt, attempt_id)
                payment = await session.scalar(select(Payment))
                order = await session.get(Order, order_id)
                product = await session.get(Product, product_id)
                assert job is not None and job.last_observed_status == "succeeded"
                assert attempt is not None and attempt.status == "pending"
                assert payment is not None and payment.status == "pending"
                assert order is not None and order.status == "new"
                assert product is not None and product.reserved_quantity == 1
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_reconciliation_rolls_back_paid_state_when_inventory_expired(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "expired.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, product_id, attempt_id, job_id = await _seed_active_attempt(
                database,
                created_at=created_at,
            )
            due_at = created_at + timedelta(seconds=301)
            async with database.session() as session:
                reservation = await session.scalar(select(InventoryReservation))
                assert reservation is not None
                reservation.expires_at = due_at - timedelta(seconds=1)
                await session.commit()

            processor = PaymentReconciliationProcessor(
                settings,
                SequenceProvider([_snapshot(order_id, status="succeeded")]),
            )
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="expired-worker",
                    now=due_at,
                )
            assert result is not None and result.status == "dead"
            assert result.error_code == "paid_order_transition_failed"

            async with database.session() as session:
                job = await session.get(PaymentReconciliationJob, job_id)
                attempt = await session.get(PaymentAttempt, attempt_id)
                payment = await session.scalar(select(Payment))
                order = await session.get(Order, order_id)
                product = await session.get(Product, product_id)
                reservation = await session.scalar(select(InventoryReservation))
                assert job is not None and job.last_observed_status == "succeeded"
                assert attempt is not None and attempt.status == "pending"
                assert payment is not None and payment.status == "pending"
                assert order is not None and order.status == "new"
                assert order.payment_status == "pending"
                assert product is not None and product.stock_quantity == 3
                assert product.reserved_quantity == 1
                assert reservation is not None and reservation.status == "active"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_reconciliation_reaps_crashed_final_attempt_without_provider_call(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "stale.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            order_id, _, _, job_id = await _seed_active_attempt(
                database,
                created_at=created_at,
            )
            due_at = created_at + timedelta(seconds=301)
            async with database.session() as session:
                job = await session.get(PaymentReconciliationJob, job_id)
                assert job is not None
                job.max_attempts = 1
                await session.commit()
            async with database.session() as session:
                claimed = await PaymentRepository().claim_next_reconciliation_job(
                    session,
                    now=due_at,
                    stale_before=due_at - timedelta(seconds=300),
                    worker_id="crashed-worker",
                )
                assert claimed is not None and claimed.attempts_count == 1
                await session.commit()

            provider = SequenceProvider([_snapshot(order_id, status="succeeded")])
            processor = PaymentReconciliationProcessor(settings, provider)
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="reaper",
                    now=due_at + timedelta(seconds=301),
                )
            assert result is not None and result.status == "dead"
            assert result.error_code == "reconciliation_stale_exhausted"
            assert result.attempt_number == 1 and provider.calls == 0
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_reconciliation_seeds_only_provider_linked_active_attempts(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "seed.db")
        database = DatabaseManager(settings)
        await database.startup()
        created_at = datetime.now(timezone.utc)
        try:
            _, _, attempt_id, job_id = await _seed_active_attempt(
                database,
                created_at=created_at,
            )
            async with database.session() as session:
                job = await session.get(PaymentReconciliationJob, job_id)
                attempt = await session.get(PaymentAttempt, attempt_id)
                assert job is not None and attempt is not None
                await session.delete(job)
                attempt.status = "unknown"
                attempt.provider_payment_id = None
                await session.commit()

            processor = PaymentReconciliationProcessor(settings, SequenceProvider([]))
            async with database.session() as session:
                assert await processor.seed_missing_jobs(session, now=created_at) == 0
            async with database.session() as session:
                attempt = await session.get(PaymentAttempt, attempt_id)
                assert attempt is not None
                attempt.provider_payment_id = PROVIDER_PAYMENT_ID
                await session.commit()
            async with database.session() as session:
                assert await processor.seed_missing_jobs(session, now=created_at) == 1
            async with database.session() as session:
                assert await processor.seed_missing_jobs(session, now=created_at) == 0
                job = await session.scalar(select(PaymentReconciliationJob))
                assert job is not None and job.status == "scheduled"
                assert job.available_at == created_at.replace(tzinfo=None)
        finally:
            await database.shutdown()

    asyncio.run(scenario())
