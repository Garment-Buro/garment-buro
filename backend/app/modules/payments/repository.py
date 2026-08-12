from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.orders.models import LegacyOrderImport, Order
from app.modules.payments.models import (
    Payment,
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentEvent,
    PaymentEventStatus,
    PaymentReconciliationJob,
    PaymentReconciliationStatus,
)


class PaymentRepository:
    async def get_order_for_update(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> Order | None:
        return await session.scalar(select(Order).where(Order.id == order_id).with_for_update())

    async def get_order_with_items_for_update(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> Order | None:
        return await session.scalar(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
            .with_for_update()
        )

    async def is_legacy_import(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> bool:
        return bool(
            await session.scalar(
                select(LegacyOrderImport.id).where(LegacyOrderImport.order_id == order_id)
            )
        )

    async def get_payment_for_update(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> Payment | None:
        return await session.scalar(
            select(Payment).where(Payment.order_id == order_id).with_for_update()
        )

    @staticmethod
    async def add_payment(session: AsyncSession, payment: Payment) -> None:
        session.add(payment)
        await session.flush()

    async def get_attempt_by_client_digest(
        self,
        session: AsyncSession,
        *,
        client_key_digest_sha256: str,
        for_update: bool = False,
    ) -> PaymentAttempt | None:
        statement = (
            select(PaymentAttempt)
            .where(PaymentAttempt.client_key_digest_sha256 == client_key_digest_sha256)
            .options(selectinload(PaymentAttempt.payment))
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def get_open_attempt(
        self,
        session: AsyncSession,
        *,
        payment_id: int,
    ) -> PaymentAttempt | None:
        return await session.scalar(
            select(PaymentAttempt)
            .where(
                PaymentAttempt.payment_id == payment_id,
                PaymentAttempt.status.in_(
                    (
                        PaymentAttemptStatus.PREPARED.value,
                        PaymentAttemptStatus.UNKNOWN.value,
                        PaymentAttemptStatus.PENDING.value,
                        PaymentAttemptStatus.WAITING_FOR_CAPTURE.value,
                    )
                ),
            )
            .order_by(PaymentAttempt.attempt_number.desc())
            .limit(1)
        )

    async def next_attempt_number(
        self,
        session: AsyncSession,
        *,
        payment_id: int,
    ) -> int:
        current = await session.scalar(
            select(func.max(PaymentAttempt.attempt_number)).where(
                PaymentAttempt.payment_id == payment_id
            )
        )
        return int(current or 0) + 1

    async def add_attempt(
        self,
        session: AsyncSession,
        attempt: PaymentAttempt,
    ) -> tuple[PaymentAttempt, bool]:
        try:
            async with session.begin_nested():
                session.add(attempt)
                await session.flush()
            return attempt, True
        except IntegrityError:
            existing = await self.get_attempt_by_client_digest(
                session,
                client_key_digest_sha256=attempt.client_key_digest_sha256,
                for_update=True,
            )
            if existing is None:
                raise
            return existing, False

    async def get_attempt_for_update(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
    ) -> PaymentAttempt | None:
        return await session.scalar(
            select(PaymentAttempt)
            .where(PaymentAttempt.id == attempt_id)
            .options(selectinload(PaymentAttempt.payment))
            .with_for_update()
        )

    async def get_latest_attempt_for_update(
        self,
        session: AsyncSession,
        *,
        payment_id: int,
    ) -> PaymentAttempt | None:
        return await session.scalar(
            select(PaymentAttempt)
            .where(PaymentAttempt.payment_id == payment_id)
            .order_by(PaymentAttempt.attempt_number.desc())
            .limit(1)
            .with_for_update()
        )

    async def find_attempt_by_provider_id(
        self,
        session: AsyncSession,
        *,
        provider_payment_id: str,
    ) -> PaymentAttempt | None:
        return await session.scalar(
            select(PaymentAttempt).where(PaymentAttempt.provider_payment_id == provider_payment_id)
        )

    async def get_attempt_by_provider_id_for_update(
        self,
        session: AsyncSession,
        *,
        provider_payment_id: str,
    ) -> PaymentAttempt | None:
        return await session.scalar(
            select(PaymentAttempt)
            .where(PaymentAttempt.provider_payment_id == provider_payment_id)
            .options(selectinload(PaymentAttempt.payment))
            .with_for_update()
        )

    async def get_reconciliation_job_for_attempt_for_update(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
    ) -> PaymentReconciliationJob | None:
        return await session.scalar(
            select(PaymentReconciliationJob)
            .where(PaymentReconciliationJob.payment_attempt_id == attempt_id)
            .with_for_update()
        )

    async def ensure_reconciliation_job(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        available_at: datetime,
        max_attempts: int,
    ) -> tuple[PaymentReconciliationJob, bool]:
        existing = await self.get_reconciliation_job_for_attempt_for_update(
            session,
            attempt_id=attempt_id,
        )
        if existing is not None:
            return existing, False
        job = PaymentReconciliationJob(
            payment_attempt_id=attempt_id,
            status=PaymentReconciliationStatus.SCHEDULED.value,
            max_attempts=max_attempts,
            available_at=available_at,
        )
        try:
            async with session.begin_nested():
                session.add(job)
                await session.flush()
            return job, True
        except IntegrityError:
            existing = await self.get_reconciliation_job_for_attempt_for_update(
                session,
                attempt_id=attempt_id,
            )
            if existing is None:
                raise
            return existing, False

    async def seed_missing_reconciliation_jobs(
        self,
        session: AsyncSession,
        *,
        available_at: datetime,
        max_attempts: int,
        limit: int,
    ) -> int:
        attempts = list(
            await session.scalars(
                select(PaymentAttempt)
                .join(Payment, Payment.id == PaymentAttempt.payment_id)
                .outerjoin(
                    LegacyOrderImport,
                    LegacyOrderImport.order_id == Payment.order_id,
                )
                .outerjoin(
                    PaymentReconciliationJob,
                    PaymentReconciliationJob.payment_attempt_id == PaymentAttempt.id,
                )
                .where(
                    PaymentReconciliationJob.id.is_(None),
                    LegacyOrderImport.id.is_(None),
                    PaymentAttempt.provider_payment_id.is_not(None),
                    PaymentAttempt.status.in_(
                        (
                            PaymentAttemptStatus.UNKNOWN.value,
                            PaymentAttemptStatus.PENDING.value,
                            PaymentAttemptStatus.WAITING_FOR_CAPTURE.value,
                        )
                    ),
                )
                .order_by(PaymentAttempt.id)
                .limit(limit)
                .with_for_update(of=PaymentAttempt, skip_locked=True)
            )
        )
        inserted = 0
        for attempt in attempts:
            _, created = await self.ensure_reconciliation_job(
                session,
                attempt_id=attempt.id,
                available_at=available_at,
                max_attempts=max_attempts,
            )
            inserted += int(created)
        return inserted

    async def claim_next_reconciliation_job(
        self,
        session: AsyncSession,
        *,
        now: datetime,
        stale_before: datetime,
        worker_id: str,
    ) -> PaymentReconciliationJob | None:
        job = await session.scalar(
            select(PaymentReconciliationJob)
            .where(
                or_(
                    (
                        PaymentReconciliationJob.status.in_(
                            (
                                PaymentReconciliationStatus.SCHEDULED.value,
                                PaymentReconciliationStatus.RETRY.value,
                            )
                        )
                        & (PaymentReconciliationJob.available_at <= now)
                        & (
                            PaymentReconciliationJob.attempts_count
                            < PaymentReconciliationJob.max_attempts
                        )
                    ),
                    (
                        PaymentReconciliationJob.status
                        == PaymentReconciliationStatus.PROCESSING.value
                    )
                    & (PaymentReconciliationJob.locked_at <= stale_before),
                )
            )
            .options(selectinload(PaymentReconciliationJob.attempt))
            .order_by(PaymentReconciliationJob.available_at, PaymentReconciliationJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        if (
            job.status == PaymentReconciliationStatus.PROCESSING.value
            and job.attempts_count >= job.max_attempts
        ):
            job.status = PaymentReconciliationStatus.DEAD.value
            job.locked_at = None
            job.locked_by = None
            job.completed_at = None
            job.last_error_code = "reconciliation_stale_exhausted"
            await session.flush()
            return job
        job.status = PaymentReconciliationStatus.PROCESSING.value
        job.attempts_count += 1
        job.locked_at = now
        job.locked_by = worker_id
        job.completed_at = None
        await session.flush()
        return job

    async def get_reconciliation_job_for_update(
        self,
        session: AsyncSession,
        *,
        job_id: int,
    ) -> PaymentReconciliationJob | None:
        return await session.scalar(
            select(PaymentReconciliationJob)
            .where(PaymentReconciliationJob.id == job_id)
            .with_for_update()
        )

    @staticmethod
    async def mark_reconciliation_scheduled(
        session: AsyncSession,
        job: PaymentReconciliationJob,
        *,
        available_at: datetime,
        checked_at: datetime,
        observation_sha256: str,
        observed_status: str,
    ) -> None:
        if job.attempts_count >= job.max_attempts:
            job.status = PaymentReconciliationStatus.DEAD.value
            job.last_error_code = "active_window_exhausted"
        else:
            job.status = PaymentReconciliationStatus.SCHEDULED.value
            job.last_error_code = None
        job.available_at = available_at
        job.last_checked_at = checked_at
        job.last_observation_sha256 = observation_sha256
        job.last_observed_status = observed_status
        job.completed_at = None
        job.locked_at = None
        job.locked_by = None
        await session.flush()

    @staticmethod
    async def mark_reconciliation_completed(
        session: AsyncSession,
        job: PaymentReconciliationJob,
        *,
        completed_at: datetime,
        observation_sha256: str | None = None,
        observed_status: str | None = None,
    ) -> None:
        job.status = PaymentReconciliationStatus.COMPLETED.value
        job.last_checked_at = (
            completed_at if observation_sha256 is not None else job.last_checked_at
        )
        job.completed_at = completed_at
        if observation_sha256 is not None:
            job.last_observation_sha256 = observation_sha256
            job.last_observed_status = observed_status
        job.last_error_code = None
        job.locked_at = None
        job.locked_by = None
        await session.flush()

    @staticmethod
    async def mark_reconciliation_failed(
        session: AsyncSession,
        job: PaymentReconciliationJob,
        *,
        available_at: datetime,
        checked_at: datetime | None,
        error_code: str,
        permanent: bool,
        observation_sha256: str | None = None,
        observed_status: str | None = None,
    ) -> None:
        if permanent or job.attempts_count >= job.max_attempts:
            job.status = PaymentReconciliationStatus.DEAD.value
        else:
            job.status = PaymentReconciliationStatus.RETRY.value
        job.available_at = available_at
        job.last_checked_at = checked_at or job.last_checked_at
        if observation_sha256 is not None:
            job.last_observation_sha256 = observation_sha256
            job.last_observed_status = observed_status
        job.completed_at = None
        job.locked_at = None
        job.locked_by = None
        job.last_error_code = error_code
        await session.flush()

    async def add_event(
        self,
        session: AsyncSession,
        event: PaymentEvent,
    ) -> tuple[PaymentEvent, bool]:
        try:
            async with session.begin_nested():
                session.add(event)
                await session.flush()
            return event, True
        except IntegrityError:
            existing = await session.scalar(
                select(PaymentEvent)
                .where(PaymentEvent.event_key_sha256 == event.event_key_sha256)
                .with_for_update()
            )
            if existing is None:
                raise
            return existing, False

    async def claim_next_event(
        self,
        session: AsyncSession,
        *,
        now: datetime,
        stale_before: datetime,
        worker_id: str,
    ) -> PaymentEvent | None:
        event = await session.scalar(
            select(PaymentEvent)
            .where(
                or_(
                    (
                        PaymentEvent.status.in_(
                            (
                                PaymentEventStatus.RECEIVED.value,
                                PaymentEventStatus.RETRY.value,
                            )
                        )
                        & (PaymentEvent.available_at <= now)
                        & (PaymentEvent.attempts_count < PaymentEvent.max_attempts)
                    ),
                    (
                        (PaymentEvent.status == PaymentEventStatus.PROCESSING.value)
                        & (PaymentEvent.locked_at <= stale_before)
                    ),
                ),
            )
            .order_by(PaymentEvent.available_at, PaymentEvent.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if event is None:
            return None
        if (
            event.status == PaymentEventStatus.PROCESSING.value
            and event.attempts_count >= event.max_attempts
        ):
            event.status = PaymentEventStatus.DEAD.value
            event.locked_at = None
            event.locked_by = None
            event.processed_at = None
            event.last_error_code = "worker_stale_exhausted"
            await session.flush()
            return event
        event.status = PaymentEventStatus.PROCESSING.value
        event.attempts_count += 1
        event.locked_at = now
        event.locked_by = worker_id
        event.processed_at = None
        await session.flush()
        return event

    async def get_event_for_update(
        self,
        session: AsyncSession,
        *,
        event_id: int,
    ) -> PaymentEvent | None:
        return await session.scalar(
            select(PaymentEvent).where(PaymentEvent.id == event_id).with_for_update()
        )

    @staticmethod
    async def mark_event_processed(
        session: AsyncSession,
        event: PaymentEvent,
        *,
        now: datetime,
    ) -> None:
        event.status = PaymentEventStatus.PROCESSED.value
        event.processed_at = now
        event.locked_at = None
        event.locked_by = None
        event.last_error_code = None
        await session.flush()

    @staticmethod
    async def mark_event_failed(
        session: AsyncSession,
        event: PaymentEvent,
        *,
        available_at: datetime,
        error_code: str,
        permanent: bool,
        rejected: bool,
    ) -> None:
        if rejected:
            event.status = PaymentEventStatus.REJECTED.value
        elif permanent or event.attempts_count >= event.max_attempts:
            event.status = PaymentEventStatus.DEAD.value
        else:
            event.status = PaymentEventStatus.RETRY.value
        event.available_at = available_at
        event.processed_at = None
        event.locked_at = None
        event.locked_by = None
        event.last_error_code = error_code
        await session.flush()
