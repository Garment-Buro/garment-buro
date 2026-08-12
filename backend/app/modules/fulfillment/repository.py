from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.fulfillment.models import (
    FulfillmentJob,
    FulfillmentJobAttempt,
    FulfillmentJobAttemptStatus,
    FulfillmentJobKind,
    FulfillmentJobStatus,
)
from app.modules.orders.models import (
    LegacyOrderImport,
    Order,
    OrderPaymentStatus,
    OrderStatus,
)
from app.modules.payments.models import (
    Payment,
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentStatus,
)


class FulfillmentEvidenceConflictError(RuntimeError):
    pass


class FulfillmentRepository:
    async def get_succeeded_attempt(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        attempt_id: int,
    ) -> PaymentAttempt | None:
        statement = (
            select(PaymentAttempt)
            .join(Payment, Payment.id == PaymentAttempt.payment_id)
            .where(
                PaymentAttempt.id == attempt_id,
                PaymentAttempt.status == PaymentAttemptStatus.SUCCEEDED.value,
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.SUCCEEDED.value,
            )
        )
        if session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update(of=PaymentAttempt)
        else:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def get_succeeded_payment(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        payment_id: int,
    ) -> Payment | None:
        statement = select(Payment).where(
            Payment.id == payment_id,
            Payment.order_id == order_id,
            Payment.status == PaymentStatus.SUCCEEDED.value,
        )
        if session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update(of=Payment)
        else:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def enqueue(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        source_payment_attempt_id: int,
        kind: FulfillmentJobKind,
        max_attempts: int,
        available_at: datetime,
    ) -> FulfillmentJob:
        values = {
            "order_id": order_id,
            "source_payment_attempt_id": source_payment_attempt_id,
            "kind": kind.value,
            "max_attempts": max_attempts,
            "available_at": available_at,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(FulfillmentJob).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(FulfillmentJob).values(**values)
        else:
            raise RuntimeError("Fulfillment outbox requires PostgreSQL or SQLite")
        await session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[FulfillmentJob.order_id, FulfillmentJob.kind],
            )
        )
        job = await session.scalar(
            select(FulfillmentJob)
            .where(
                FulfillmentJob.order_id == order_id,
                FulfillmentJob.kind == kind.value,
            )
            .with_for_update()
        )
        if job is None:
            raise RuntimeError("Fulfillment job could not be acquired")
        if job.source_payment_attempt_id != source_payment_attempt_id:
            raise FulfillmentEvidenceConflictError(
                "Fulfillment job is linked to another successful payment attempt"
            )
        return job

    async def list_order_jobs(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> list[FulfillmentJob]:
        return list(
            await session.scalars(
                select(FulfillmentJob)
                .where(FulfillmentJob.order_id == order_id)
                .order_by(FulfillmentJob.kind)
            )
        )

    async def list_paid_order_evidence_for_update(
        self,
        session: AsyncSession,
        *,
        limit: int,
    ) -> list[tuple[Order, PaymentAttempt]]:
        statement = (
            select(Order, PaymentAttempt)
            .join(Payment, Payment.order_id == Order.id)
            .join(PaymentAttempt, PaymentAttempt.payment_id == Payment.id)
            .outerjoin(LegacyOrderImport, LegacyOrderImport.order_id == Order.id)
            .where(
                LegacyOrderImport.id.is_(None),
                Order.payment_status == OrderPaymentStatus.PAID.value,
                Order.status.in_(
                    (
                        OrderStatus.PROCESSING.value,
                        OrderStatus.SHIPPED.value,
                        OrderStatus.COMPLETED.value,
                    )
                ),
                Payment.status == PaymentStatus.SUCCEEDED.value,
                PaymentAttempt.status == PaymentAttemptStatus.SUCCEEDED.value,
            )
            .order_by(Order.id)
            .limit(limit)
        )
        if session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update(
                of=(Order, PaymentAttempt),
                skip_locked=True,
            )
        else:
            statement = statement.with_for_update()
        rows = await session.execute(statement)
        return [(order, attempt) for order, attempt in rows.tuples()]

    async def get_paid_order_with_items_for_update(
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

    async def claim_next(
        self,
        session: AsyncSession,
        *,
        kinds: tuple[FulfillmentJobKind, ...],
        now: datetime,
        stale_before: datetime,
        worker_id: str,
    ) -> tuple[FulfillmentJob, FulfillmentJobAttempt | None] | None:
        kind_values = tuple(kind.value for kind in kinds)
        if not kind_values:
            return None
        job = await session.scalar(
            select(FulfillmentJob)
            .where(
                FulfillmentJob.kind.in_(kind_values),
                or_(
                    (
                        FulfillmentJob.status.in_(
                            (
                                FulfillmentJobStatus.PENDING.value,
                                FulfillmentJobStatus.RETRY.value,
                            )
                        )
                        & (FulfillmentJob.available_at <= now)
                    ),
                    (
                        (FulfillmentJob.status == FulfillmentJobStatus.PROCESSING.value)
                        & (FulfillmentJob.locked_at <= stale_before)
                    ),
                ),
            )
            .order_by(FulfillmentJob.available_at, FulfillmentJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        stale_processing = job.status == FulfillmentJobStatus.PROCESSING.value
        if stale_processing:
            await self._abandon_processing_attempt(session, job.id, now)
        if job.attempts_count >= job.max_attempts:
            job.status = FulfillmentJobStatus.DEAD.value
            job.locked_at = None
            job.locked_by = None
            job.completed_at = None
            job.result_reference = None
            job.last_error_code = (
                "fulfillment_stale_exhausted"
                if stale_processing
                else "fulfillment_attempts_exhausted"
            )
            job.last_error_at = now
            await session.flush()
            return job, None

        job.status = FulfillmentJobStatus.PROCESSING.value
        job.attempts_count += 1
        job.locked_at = now
        job.locked_by = worker_id
        job.completed_at = None
        job.result_reference = None
        attempt = FulfillmentJobAttempt(
            job=job,
            attempt_number=job.attempts_count,
            status=FulfillmentJobAttemptStatus.PROCESSING.value,
            started_at=now,
            worker_id=worker_id,
        )
        session.add(attempt)
        await session.flush()
        return job, attempt

    async def get_owned_processing_for_update(
        self,
        session: AsyncSession,
        *,
        job_id: int,
        worker_id: str,
    ) -> tuple[FulfillmentJob, FulfillmentJobAttempt] | None:
        job = await session.scalar(
            select(FulfillmentJob).where(FulfillmentJob.id == job_id).with_for_update()
        )
        if (
            job is None
            or job.status != FulfillmentJobStatus.PROCESSING.value
            or job.locked_by != worker_id
        ):
            return None
        attempt = await session.scalar(
            select(FulfillmentJobAttempt)
            .where(
                FulfillmentJobAttempt.job_id == job.id,
                FulfillmentJobAttempt.attempt_number == job.attempts_count,
                FulfillmentJobAttempt.status == FulfillmentJobAttemptStatus.PROCESSING.value,
                FulfillmentJobAttempt.worker_id == worker_id,
            )
            .with_for_update()
        )
        if attempt is None:
            return None
        return job, attempt

    @staticmethod
    async def mark_completed(
        session: AsyncSession,
        job: FulfillmentJob,
        attempt: FulfillmentJobAttempt,
        *,
        now: datetime,
        result_reference: str | None,
    ) -> None:
        job.status = FulfillmentJobStatus.COMPLETED.value
        job.completed_at = now
        job.result_reference = result_reference
        job.locked_at = None
        job.locked_by = None
        job.last_error_code = None
        job.last_error_at = None
        attempt.status = FulfillmentJobAttemptStatus.COMPLETED.value
        attempt.finished_at = now
        attempt.result_reference = result_reference
        await session.flush()

    @staticmethod
    async def mark_failed(
        session: AsyncSession,
        job: FulfillmentJob,
        attempt: FulfillmentJobAttempt,
        *,
        now: datetime,
        available_at: datetime,
        error_code: str,
        permanent: bool,
    ) -> None:
        terminal = permanent or job.attempts_count >= job.max_attempts
        job.status = (
            FulfillmentJobStatus.DEAD.value if terminal else FulfillmentJobStatus.RETRY.value
        )
        job.available_at = available_at
        job.locked_at = None
        job.locked_by = None
        job.completed_at = None
        job.result_reference = None
        job.last_error_code = error_code
        job.last_error_at = now
        attempt.status = (
            FulfillmentJobAttemptStatus.DEAD.value
            if terminal
            else FulfillmentJobAttemptStatus.RETRY.value
        )
        attempt.finished_at = now
        attempt.error_code = error_code
        await session.flush()

    @staticmethod
    async def _abandon_processing_attempt(
        session: AsyncSession,
        job_id: int,
        now: datetime,
    ) -> None:
        await session.execute(
            update(FulfillmentJobAttempt)
            .where(
                FulfillmentJobAttempt.job_id == job_id,
                FulfillmentJobAttempt.status == FulfillmentJobAttemptStatus.PROCESSING.value,
            )
            .values(
                status=FulfillmentJobAttemptStatus.ABANDONED.value,
                finished_at=now,
                error_code="worker_stale",
            )
        )
