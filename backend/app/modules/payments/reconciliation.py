from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.identity.security import ensure_utc
from app.modules.inventory.service import (
    InventoryReservationExpiredError,
    InventoryReservationStateError,
)
from app.modules.orders.service import (
    InvalidOrderTransitionError,
    OrderLifecycleService,
    OrderNotFoundError,
)
from app.modules.payments.models import (
    PaymentAttemptStatus,
    PaymentReconciliationJob,
    PaymentReconciliationStatus,
)
from app.modules.payments.provider import YooKassaProvider, YooKassaProviderError
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import ProviderPaymentSnapshot
from app.modules.payments.service import (
    PaymentProviderMismatchError,
    PaymentService,
    PaymentStateError,
)


@dataclass(frozen=True, slots=True)
class PaymentReconciliationPolicy:
    interval: timedelta = timedelta(minutes=5)
    retry_base: timedelta = timedelta(seconds=30)
    retry_cap: timedelta = timedelta(minutes=30)
    processing_timeout: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if self.interval <= timedelta(0):
            raise ValueError("Payment reconciliation interval must be positive")
        if self.retry_base <= timedelta(0) or self.retry_cap < self.retry_base:
            raise ValueError("Payment reconciliation retry durations are invalid")
        if self.processing_timeout <= timedelta(0):
            raise ValueError("Payment reconciliation processing timeout must be positive")

    @classmethod
    def from_settings(cls, settings: Settings) -> PaymentReconciliationPolicy:
        return cls(
            interval=timedelta(seconds=settings.payment_reconciliation_interval_seconds),
            retry_base=timedelta(seconds=settings.payment_reconciliation_retry_base_seconds),
            retry_cap=timedelta(seconds=settings.payment_reconciliation_retry_cap_seconds),
            processing_timeout=timedelta(
                seconds=settings.payment_reconciliation_processing_timeout_seconds
            ),
        )


@dataclass(frozen=True, slots=True)
class PaymentReconciliationResult:
    job_id: int
    status: str
    attempt_number: int
    observed_status: str | None = None
    error_code: str | None = None


class PaymentReconciliationOwnershipError(RuntimeError):
    pass


class PaymentReconciliationProcessor:
    def __init__(
        self,
        settings: Settings,
        provider: YooKassaProvider,
        *,
        repository: PaymentRepository | None = None,
        payment_service: PaymentService | None = None,
        order_lifecycle: OrderLifecycleService | None = None,
        policy: PaymentReconciliationPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.repository = repository or PaymentRepository()
        self.payment_service = payment_service or PaymentService(
            settings,
            repository=self.repository,
        )
        self.order_lifecycle = order_lifecycle or OrderLifecycleService(settings)
        self.policy = policy or PaymentReconciliationPolicy.from_settings(settings)

    async def seed_missing_jobs(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> int:
        if not 1 <= limit <= 1_000:
            raise ValueError("Payment reconciliation seed limit must be between 1 and 1000")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        inserted = await self.repository.seed_missing_reconciliation_jobs(
            session,
            available_at=current_time,
            max_attempts=self.settings.payment_reconciliation_max_attempts,
            limit=limit,
        )
        await session.commit()
        return inserted

    async def process_once(
        self,
        session: AsyncSession,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> PaymentReconciliationResult | None:
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        job = await self.repository.claim_next_reconciliation_job(
            session,
            now=current_time,
            stale_before=current_time - self.policy.processing_timeout,
            worker_id=worker_id,
        )
        if job is None:
            return None
        if job.status == PaymentReconciliationStatus.DEAD.value:
            await session.commit()
            return self._result(job)
        job_id = job.id
        attempt_id = job.payment_attempt_id
        attempt_number = job.attempts_count
        provider_payment_id = job.attempt.provider_payment_id
        await session.commit()

        if provider_payment_id is None:
            return await self._fail(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=current_time,
                error_code="provider_id_missing",
                permanent=True,
            )
        try:
            snapshot = await self.provider.get_payment(provider_payment_id)
        except YooKassaProviderError as error:
            return await self._fail(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=current_time,
                error_code=error.code,
                permanent=not error.retryable,
            )
        except Exception:  # noqa: BLE001 - durable reconciliation must survive provider defects
            return await self._fail(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=current_time,
                error_code="provider_unexpected",
                permanent=False,
            )

        observation_digest = self.payment_service.provider_snapshot_digest(snapshot)
        try:
            attempt = await self.repository.get_attempt_for_update(
                session,
                attempt_id=attempt_id,
            )
            locked = await self._owned_job_or_terminal(
                session,
                job_id=job_id,
                worker_id=worker_id,
            )
            if locked.status != PaymentReconciliationStatus.PROCESSING.value:
                await session.commit()
                return self._result(locked)
            if attempt is None or attempt.provider_payment_id != provider_payment_id:
                raise PaymentProviderMismatchError(
                    "Reconciliation job does not match the payment attempt"
                )
            applied = await self.payment_service.record_provider_snapshot(
                session,
                attempt_id=attempt.id,
                snapshot=snapshot,
                now=current_time,
                manage_reconciliation=False,
            )
            if snapshot.status == PaymentAttemptStatus.SUCCEEDED.value:
                await self.order_lifecycle.confirm_payment(
                    session,
                    order_id=applied.order_id,
                    payment_attempt_id=applied.attempt_id,
                    now=current_time,
                )
            if snapshot.status in {
                PaymentAttemptStatus.SUCCEEDED.value,
                PaymentAttemptStatus.CANCELED.value,
            }:
                await self.repository.mark_reconciliation_completed(
                    session,
                    locked,
                    completed_at=current_time,
                    observation_sha256=observation_digest,
                    observed_status=snapshot.status,
                )
            else:
                await self.repository.mark_reconciliation_scheduled(
                    session,
                    locked,
                    available_at=current_time + self.policy.interval,
                    checked_at=current_time,
                    observation_sha256=observation_digest,
                    observed_status=snapshot.status,
                )
            await session.commit()
            return PaymentReconciliationResult(
                job_id=job_id,
                status=locked.status,
                attempt_number=attempt_number,
                observed_status=snapshot.status,
                error_code=locked.last_error_code,
            )
        except PaymentProviderMismatchError:
            await session.rollback()
            return await self._fail(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=current_time,
                error_code="provider_evidence_mismatch",
                permanent=True,
                snapshot=snapshot,
            )
        except PaymentStateError:
            await session.rollback()
            return await self._fail(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=current_time,
                error_code="payment_state_conflict",
                permanent=True,
                snapshot=snapshot,
            )
        except (
            InventoryReservationExpiredError,
            InventoryReservationStateError,
            InvalidOrderTransitionError,
            OrderNotFoundError,
        ):
            await session.rollback()
            return await self._fail(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=current_time,
                error_code="paid_order_transition_failed",
                permanent=True,
                snapshot=snapshot,
            )
        except PaymentReconciliationOwnershipError:
            await session.rollback()
            raise
        except Exception:  # noqa: BLE001 - retry durable work after transient DB defects
            await session.rollback()
            return await self._fail(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=current_time,
                error_code="processing_unexpected",
                permanent=False,
                snapshot=snapshot,
            )

    async def _fail(
        self,
        session: AsyncSession,
        *,
        job_id: int,
        worker_id: str,
        now: datetime,
        error_code: str,
        permanent: bool,
        snapshot: ProviderPaymentSnapshot | None = None,
    ) -> PaymentReconciliationResult:
        job = await self._owned_job_or_terminal(
            session,
            job_id=job_id,
            worker_id=worker_id,
        )
        if job.status != PaymentReconciliationStatus.PROCESSING.value:
            await session.commit()
            return self._result(job)
        retry_delay = min(
            self.policy.retry_base * (2 ** max(0, job.attempts_count - 1)),
            self.policy.retry_cap,
        )
        observation_digest = (
            self.payment_service.provider_snapshot_digest(snapshot)
            if snapshot is not None
            else None
        )
        await self.repository.mark_reconciliation_failed(
            session,
            job,
            available_at=now + retry_delay,
            checked_at=now if snapshot is not None else None,
            error_code=error_code,
            permanent=permanent,
            observation_sha256=observation_digest,
            observed_status=snapshot.status if snapshot is not None else None,
        )
        await session.commit()
        return self._result(job)

    async def _owned_job_or_terminal(
        self,
        session: AsyncSession,
        *,
        job_id: int,
        worker_id: str,
    ) -> PaymentReconciliationJob:
        job = await self.repository.get_reconciliation_job_for_update(
            session,
            job_id=job_id,
        )
        if job is None:
            raise PaymentReconciliationOwnershipError("Payment reconciliation job disappeared")
        if job.status in {
            PaymentReconciliationStatus.COMPLETED.value,
            PaymentReconciliationStatus.DEAD.value,
        }:
            return job
        if job.status != PaymentReconciliationStatus.PROCESSING.value or job.locked_by != worker_id:
            raise PaymentReconciliationOwnershipError(
                "Payment reconciliation worker no longer owns the claimed job"
            )
        return job

    @staticmethod
    def _result(job: PaymentReconciliationJob) -> PaymentReconciliationResult:
        return PaymentReconciliationResult(
            job_id=job.id,
            status=job.status,
            attempt_number=job.attempts_count,
            observed_status=job.last_observed_status,
            error_code=job.last_error_code,
        )
