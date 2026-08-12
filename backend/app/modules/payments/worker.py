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
from app.modules.payments.models import PaymentAttemptStatus, PaymentEvent, PaymentEventStatus
from app.modules.payments.provider import YooKassaProvider, YooKassaProviderError
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import ProviderPaymentSnapshot
from app.modules.payments.service import (
    PaymentProviderMismatchError,
    PaymentService,
    PaymentStateError,
)


@dataclass(frozen=True, slots=True)
class PaymentEventPolicy:
    retry_base: timedelta = timedelta(seconds=30)
    retry_cap: timedelta = timedelta(minutes=30)
    processing_timeout: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if self.retry_base <= timedelta(0) or self.retry_cap < self.retry_base:
            raise ValueError("Payment event retry durations are invalid")
        if self.processing_timeout <= timedelta(0):
            raise ValueError("Payment event processing timeout must be positive")

    @classmethod
    def from_settings(cls, settings: Settings) -> PaymentEventPolicy:
        return cls(
            retry_base=timedelta(seconds=settings.payment_event_retry_base_seconds),
            retry_cap=timedelta(seconds=settings.payment_event_retry_cap_seconds),
            processing_timeout=timedelta(seconds=settings.payment_event_processing_timeout_seconds),
        )


@dataclass(frozen=True, slots=True)
class PaymentEventProcessingResult:
    event_id: int
    status: str
    attempt_number: int
    error_code: str | None = None


class PaymentEventOwnershipError(RuntimeError):
    pass


class PaymentEventProcessor:
    def __init__(
        self,
        settings: Settings,
        provider: YooKassaProvider,
        *,
        repository: PaymentRepository | None = None,
        payment_service: PaymentService | None = None,
        order_lifecycle: OrderLifecycleService | None = None,
        policy: PaymentEventPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.repository = repository or PaymentRepository()
        self.payment_service = payment_service or PaymentService(
            settings,
            repository=self.repository,
        )
        self.order_lifecycle = order_lifecycle or OrderLifecycleService(settings)
        self.policy = policy or PaymentEventPolicy.from_settings(settings)

    async def process_once(
        self,
        session: AsyncSession,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> PaymentEventProcessingResult | None:
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        event = await self.repository.claim_next_event(
            session,
            now=current_time,
            stale_before=current_time - self.policy.processing_timeout,
            worker_id=worker_id,
        )
        if event is None:
            return None
        if event.status == PaymentEventStatus.DEAD.value:
            await session.commit()
            return PaymentEventProcessingResult(
                event_id=event.id,
                status=event.status,
                attempt_number=event.attempts_count,
                error_code=event.last_error_code,
            )
        event_id = event.id
        provider_payment_id = event.provider_payment_id
        attempt_number = event.attempts_count
        await session.commit()

        try:
            snapshot = await self.provider.get_payment(provider_payment_id)
        except YooKassaProviderError as error:
            return await self._fail(
                session,
                event_id=event_id,
                worker_id=worker_id,
                now=current_time,
                error_code=error.code,
                permanent=not error.retryable,
                rejected=error.rejected,
            )
        except Exception:  # noqa: BLE001 - provider defects must not lose a durable event
            return await self._fail(
                session,
                event_id=event_id,
                worker_id=worker_id,
                now=current_time,
                error_code="provider_unexpected",
                permanent=False,
                rejected=False,
            )

        if snapshot.status == PaymentAttemptStatus.PENDING.value:
            return await self._fail(
                session,
                event_id=event_id,
                worker_id=worker_id,
                now=current_time,
                error_code="provider_pending",
                permanent=False,
                rejected=False,
            )

        try:
            locked = await self._locked_event(session, event_id=event_id, worker_id=worker_id)
            attempt = await self.repository.get_attempt_by_provider_id_for_update(
                session,
                provider_payment_id=provider_payment_id,
            )
            if attempt is None:
                await session.rollback()
                return await self._fail(
                    session,
                    event_id=event_id,
                    worker_id=worker_id,
                    now=current_time,
                    error_code="attempt_not_found",
                    permanent=True,
                    rejected=True,
                )
            if locked.payment_attempt_id not in {None, attempt.id}:
                raise PaymentProviderMismatchError("Event is linked to another payment attempt")
            self._verify_observation(locked, snapshot)
            locked.payment_attempt_id = attempt.id
            await self.payment_service.record_provider_snapshot(
                session,
                attempt_id=attempt.id,
                snapshot=snapshot,
                now=current_time,
            )
            if snapshot.status == PaymentAttemptStatus.SUCCEEDED.value:
                await self.order_lifecycle.confirm_payment(
                    session,
                    order_id=attempt.payment.order_id,
                    payment_attempt_id=attempt.id,
                    now=current_time,
                )
            await self.repository.mark_event_processed(
                session,
                locked,
                now=current_time,
            )
            await session.commit()
            return PaymentEventProcessingResult(
                event_id=event_id,
                status=PaymentEventStatus.PROCESSED.value,
                attempt_number=attempt_number,
            )
        except PaymentProviderMismatchError:
            await session.rollback()
            return await self._fail(
                session,
                event_id=event_id,
                worker_id=worker_id,
                now=current_time,
                error_code="provider_evidence_mismatch",
                permanent=True,
                rejected=True,
            )
        except PaymentStateError:
            await session.rollback()
            return await self._fail(
                session,
                event_id=event_id,
                worker_id=worker_id,
                now=current_time,
                error_code="payment_state_conflict",
                permanent=True,
                rejected=True,
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
                event_id=event_id,
                worker_id=worker_id,
                now=current_time,
                error_code="paid_order_transition_failed",
                permanent=True,
                rejected=False,
            )
        except PaymentEventOwnershipError:
            await session.rollback()
            raise
        except Exception:  # noqa: BLE001 - retry durable work after transient DB defects
            await session.rollback()
            return await self._fail(
                session,
                event_id=event_id,
                worker_id=worker_id,
                now=current_time,
                error_code="processing_unexpected",
                permanent=False,
                rejected=False,
            )

    async def _fail(
        self,
        session: AsyncSession,
        *,
        event_id: int,
        worker_id: str,
        now: datetime,
        error_code: str,
        permanent: bool,
        rejected: bool,
    ) -> PaymentEventProcessingResult:
        event = await self._locked_event(session, event_id=event_id, worker_id=worker_id)
        retry_delay = min(
            self.policy.retry_base * (2 ** max(0, event.attempts_count - 1)),
            self.policy.retry_cap,
        )
        await self.repository.mark_event_failed(
            session,
            event,
            available_at=now + retry_delay,
            error_code=error_code,
            permanent=permanent,
            rejected=rejected,
        )
        await session.commit()
        return PaymentEventProcessingResult(
            event_id=event.id,
            status=event.status,
            attempt_number=event.attempts_count,
            error_code=error_code,
        )

    async def _locked_event(
        self,
        session: AsyncSession,
        *,
        event_id: int,
        worker_id: str,
    ) -> PaymentEvent:
        event = await self.repository.get_event_for_update(session, event_id=event_id)
        if (
            event is None
            or event.status != PaymentEventStatus.PROCESSING.value
            or event.locked_by != worker_id
        ):
            raise PaymentEventOwnershipError(
                "Payment event worker no longer owns the claimed event"
            )
        return event

    @staticmethod
    def _verify_observation(
        event: PaymentEvent,
        snapshot: ProviderPaymentSnapshot,
    ) -> None:
        if (
            event.provider_payment_id != snapshot.provider_payment_id
            or event.metadata_order_id != snapshot.metadata_order_id
            or event.observed_amount != snapshot.amount
            or event.observed_currency != snapshot.currency
            or event.observed_test != snapshot.test
        ):
            raise PaymentProviderMismatchError("Webhook observation differs from provider state")
        allowed_current = {
            PaymentAttemptStatus.WAITING_FOR_CAPTURE.value: {
                PaymentAttemptStatus.WAITING_FOR_CAPTURE.value,
                PaymentAttemptStatus.SUCCEEDED.value,
                PaymentAttemptStatus.CANCELED.value,
            },
            PaymentAttemptStatus.SUCCEEDED.value: {PaymentAttemptStatus.SUCCEEDED.value},
            PaymentAttemptStatus.CANCELED.value: {PaymentAttemptStatus.CANCELED.value},
        }
        if snapshot.status not in allowed_current.get(event.observed_status, set()):
            raise PaymentProviderMismatchError("Webhook status conflicts with provider state")
