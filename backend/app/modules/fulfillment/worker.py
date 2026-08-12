from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.fulfillment.contracts import (
    SAFE_FULFILLMENT_REFERENCE,
    FulfillmentHandler,
    FulfillmentHandlerError,
)
from app.modules.fulfillment.models import FulfillmentJob, FulfillmentJobKind, FulfillmentJobStatus
from app.modules.fulfillment.repository import FulfillmentRepository
from app.modules.identity.security import ensure_utc


@dataclass(frozen=True, slots=True)
class FulfillmentWorkerPolicy:
    retry_base: timedelta = timedelta(seconds=30)
    retry_cap: timedelta = timedelta(minutes=30)
    processing_timeout: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if self.retry_base <= timedelta(0) or self.retry_cap < self.retry_base:
            raise ValueError("Fulfillment retry durations are invalid")
        if self.processing_timeout <= timedelta(0):
            raise ValueError("Fulfillment processing timeout must be positive")

    @classmethod
    def from_settings(cls, settings: Settings) -> FulfillmentWorkerPolicy:
        return cls(
            retry_base=timedelta(seconds=settings.fulfillment_retry_base_seconds),
            retry_cap=timedelta(seconds=settings.fulfillment_retry_cap_seconds),
            processing_timeout=timedelta(seconds=settings.fulfillment_processing_timeout_seconds),
        )


@dataclass(frozen=True, slots=True)
class FulfillmentProcessingResult:
    job_id: int
    kind: str
    status: str
    attempt_number: int
    error_code: str | None = None
    result_reference: str | None = None


class FulfillmentOwnershipError(RuntimeError):
    pass


class FulfillmentProcessor:
    """Claim durable jobs and atomically hand them to local durable domains."""

    def __init__(
        self,
        settings: Settings,
        handlers: tuple[FulfillmentHandler, ...],
        *,
        repository: FulfillmentRepository | None = None,
        policy: FulfillmentWorkerPolicy | None = None,
    ) -> None:
        if not handlers:
            raise ValueError("At least one fulfillment handler is required")
        by_kind = {handler.kind: handler for handler in handlers}
        if len(by_kind) != len(handlers):
            raise ValueError("Fulfillment handler kinds must be unique")
        self.settings = settings
        self.handlers = by_kind
        self.repository = repository or FulfillmentRepository()
        self.policy = policy or FulfillmentWorkerPolicy.from_settings(settings)

    async def process_once(
        self,
        session: AsyncSession,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> FulfillmentProcessingResult | None:
        if not worker_id or len(worker_id) > 128:
            raise ValueError("Fulfillment worker ID must contain 1-128 characters")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        claimed = await self.repository.claim_next(
            session,
            kinds=tuple(self.handlers),
            now=current_time,
            stale_before=current_time - self.policy.processing_timeout,
            worker_id=worker_id,
        )
        if claimed is None:
            return None
        job, _attempt = claimed
        if job.status == FulfillmentJobStatus.DEAD.value:
            await session.commit()
            return self._result(job)

        job_id = job.id
        kind = FulfillmentJobKind(job.kind)
        handler = self.handlers[kind]
        attempt_number = job.attempts_count
        await session.commit()

        try:
            prepared = await handler.prepare(
                session,
                job,
                now=current_time,
            )
            owned = await self.repository.get_owned_processing_for_update(
                session,
                job_id=job_id,
                worker_id=worker_id,
            )
            if owned is None:
                raise FulfillmentOwnershipError("Fulfillment job is no longer owned by this worker")
            locked, locked_attempt = owned
            result_reference = await handler.apply(
                session,
                locked,
                prepared,
                now=current_time,
            )
            if result_reference is not None and not SAFE_FULFILLMENT_REFERENCE.fullmatch(
                result_reference
            ):
                raise FulfillmentHandlerError("result_reference_invalid", permanent=True)
            await self.repository.mark_completed(
                session,
                locked,
                locked_attempt,
                now=current_time,
                result_reference=result_reference,
            )
            await session.commit()
            return FulfillmentProcessingResult(
                job_id=job_id,
                kind=kind.value,
                status=FulfillmentJobStatus.COMPLETED.value,
                attempt_number=attempt_number,
                result_reference=result_reference,
            )
        except FulfillmentHandlerError as error:
            await session.rollback()
            return await self._fail(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=current_time,
                kind=kind,
                error_code=error.code,
                permanent=error.permanent,
            )
        except FulfillmentOwnershipError:
            await session.rollback()
            raise
        except Exception:  # noqa: BLE001 - one durable job must not stop the worker
            await session.rollback()
            return await self._fail(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=current_time,
                kind=kind,
                error_code="handler_unexpected",
                permanent=False,
            )

    async def _fail(
        self,
        session: AsyncSession,
        *,
        job_id: int,
        worker_id: str,
        now: datetime,
        kind: FulfillmentJobKind,
        error_code: str,
        permanent: bool,
    ) -> FulfillmentProcessingResult:
        owned = await self.repository.get_owned_processing_for_update(
            session,
            job_id=job_id,
            worker_id=worker_id,
        )
        if owned is None:
            raise FulfillmentOwnershipError(
                "Fulfillment failure cannot mutate a job owned by another worker"
            )
        job, attempt = owned
        retry_delay = min(
            self.policy.retry_base * (2 ** max(0, job.attempts_count - 1)),
            self.policy.retry_cap,
        )
        await self.repository.mark_failed(
            session,
            job,
            attempt,
            now=now,
            available_at=now + retry_delay,
            error_code=error_code,
            permanent=permanent,
        )
        await session.commit()
        return self._result(job, kind=kind)

    @staticmethod
    def _result(
        job: FulfillmentJob,
        *,
        kind: FulfillmentJobKind | None = None,
    ) -> FulfillmentProcessingResult:
        return FulfillmentProcessingResult(
            job_id=job.id,
            kind=(kind.value if kind is not None else job.kind),
            status=job.status,
            attempt_number=job.attempts_count,
            error_code=job.last_error_code,
            result_reference=job.result_reference,
        )
