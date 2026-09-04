from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
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
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentCaptureMode,
    PaymentOperation,
    PaymentOperationStatus,
    PaymentOperationType,
)
from app.modules.payments.operation_repository import PaymentOperationRepository
from app.modules.payments.provider import YooKassaProvider, YooKassaProviderError
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.security import digest_payment_attempt_key
from app.modules.payments.service import (
    PaymentProviderMismatchError,
    PaymentService,
    PaymentStateError,
)


class PaymentOperationDisabledError(RuntimeError):
    pass


class PaymentOperationConflictError(ValueError):
    pass


class PaymentOperationInProgressError(RuntimeError):
    pass


class PaymentOperationFailedError(RuntimeError):
    def __init__(self, code: str, *, outcome_unknown: bool) -> None:
        super().__init__(f"Payment operation failed: {code}")
        self.code = code
        self.outcome_unknown = outcome_unknown


@dataclass(frozen=True, slots=True)
class PaymentOperationResult:
    operation_id: int
    payment_attempt_id: int
    order_id: int
    operation: str
    operation_status: str
    payment_status: str
    provider_payment_id: str
    capture_expires_at: datetime | None
    replayed: bool


@dataclass(frozen=True, slots=True)
class OrderPaymentResult:
    payment_id: int
    payment_attempt_id: int
    order_id: int
    capture_mode: str
    status: str
    provider_payment_id: str | None
    confirmation_url: str | None
    capture_expires_at: datetime | None


class PaymentOperationService:
    """Durably capture or cancel a manually captured YooKassa payment."""

    def __init__(
        self,
        settings: Settings,
        provider: YooKassaProvider,
        *,
        repository: PaymentOperationRepository | None = None,
        payment_repository: PaymentRepository | None = None,
        payment_service: PaymentService | None = None,
        order_lifecycle: OrderLifecycleService | None = None,
        provider_key_factory: Callable[[], str] | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.repository = repository or PaymentOperationRepository()
        self.payment_repository = payment_repository or PaymentRepository()
        self.payment_service = payment_service or PaymentService(
            settings,
            repository=self.payment_repository,
        )
        self.order_lifecycle = order_lifecycle or OrderLifecycleService(settings)
        self.provider_key_factory = provider_key_factory or (lambda: str(uuid.uuid4()))

    async def capture(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        client_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> PaymentOperationResult:
        return await self._execute(
            session,
            attempt_id=attempt_id,
            operation_type=PaymentOperationType.CAPTURE,
            client_key=client_key,
            actor_user_id=actor_user_id,
            now=now,
        )

    async def capture_order(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        client_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> PaymentOperationResult:
        return await self.capture(
            session,
            attempt_id=await self._latest_attempt_id(session, order_id=order_id),
            client_key=client_key,
            actor_user_id=actor_user_id,
            now=now,
        )

    async def cancel(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        client_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> PaymentOperationResult:
        return await self._execute(
            session,
            attempt_id=attempt_id,
            operation_type=PaymentOperationType.CANCEL,
            client_key=client_key,
            actor_user_id=actor_user_id,
            now=now,
        )

    async def cancel_order(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        client_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> PaymentOperationResult:
        return await self.cancel(
            session,
            attempt_id=await self._latest_attempt_id(session, order_id=order_id),
            client_key=client_key,
            actor_user_id=actor_user_id,
            now=now,
        )

    async def get_order_payment(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> OrderPaymentResult:
        if not self.settings.payment_management_enabled:
            raise PaymentOperationDisabledError("Payment management is disabled")
        payment = await self.payment_repository.get_payment_for_update(
            session,
            order_id=order_id,
        )
        if payment is None:
            raise PaymentStateError("Order payment does not exist")
        attempt = await self.payment_repository.get_latest_attempt_for_update(
            session,
            payment_id=payment.id,
        )
        if attempt is None:
            raise PaymentStateError("Order payment attempt does not exist")
        return OrderPaymentResult(
            payment_id=payment.id,
            payment_attempt_id=attempt.id,
            order_id=order_id,
            capture_mode=attempt.capture_mode,
            status=attempt.status,
            provider_payment_id=attempt.provider_payment_id,
            confirmation_url=attempt.confirmation_url,
            capture_expires_at=attempt.expires_at,
        )

    async def _execute(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        operation_type: PaymentOperationType,
        client_key: str,
        actor_user_id: int,
        now: datetime | None,
    ) -> PaymentOperationResult:
        if not self.settings.payment_management_enabled:
            raise PaymentOperationDisabledError("Payment management is disabled")
        if attempt_id <= 0 or actor_user_id <= 0:
            raise PaymentOperationConflictError("Payment operation target is invalid")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        client_digest = digest_payment_attempt_key(client_key)
        attempt = await self.payment_repository.get_attempt_for_update(
            session,
            attempt_id=attempt_id,
        )
        if attempt is None:
            raise PaymentStateError("Payment attempt does not exist")
        request_digest = self._request_digest(attempt, operation_type)

        operation = await self.repository.get_by_client_digest(
            session,
            client_key_digest_sha256=client_digest,
            for_update=True,
        )
        if operation is None:
            operation = await self.repository.get_by_attempt(
                session,
                payment_attempt_id=attempt.id,
                for_update=True,
            )
        if operation is None:
            operation = PaymentOperation(
                payment_attempt_id=attempt.id,
                actor_user_id=actor_user_id,
                operation_type=operation_type.value,
                status=PaymentOperationStatus.PREPARED.value,
                client_key_digest_sha256=client_digest,
                provider_idempotence_key=self._provider_key(),
                request_sha256=request_digest,
                attempts_count=1,
                started_at=current_time,
                last_attempt_at=current_time,
            )
            operation, inserted = await self.repository.add(session, operation)
        else:
            inserted = False

        self._validate_replay(
            operation,
            attempt_id=attempt.id,
            operation_type=operation_type,
            client_digest=client_digest,
            request_digest=request_digest,
            actor_user_id=actor_user_id,
        )
        if not inserted:
            if operation.status == PaymentOperationStatus.SUCCEEDED.value:
                return self._result(operation, replayed=True)
            if operation.status == PaymentOperationStatus.FAILED.value:
                raise PaymentOperationFailedError(
                    operation.last_error_code or "operation_failed",
                    outcome_unknown=False,
                )
            reconciled = await self._reconcile_operation_from_attempt(
                session,
                operation=operation,
                attempt=attempt,
                operation_type=operation_type,
                now=current_time,
            )
            if reconciled is not None:
                return reconciled
            self._validate_attempt(
                attempt,
                operation_type=operation_type,
                now=current_time,
            )
            if current_time - ensure_utc(operation.last_attempt_at) < timedelta(
                seconds=self.settings.payment_operation_processing_timeout_seconds
            ):
                raise PaymentOperationInProgressError("Payment operation is already in progress")
            operation.attempts_count += 1
            operation.last_attempt_at = current_time
            operation.status = PaymentOperationStatus.PREPARED.value
            operation.last_error_code = None
        else:
            self._validate_attempt(
                attempt,
                operation_type=operation_type,
                now=current_time,
            )
        await session.commit()
        operation_id = operation.id

        try:
            snapshot = await self._call_provider(operation, attempt)
        except YooKassaProviderError as error:
            await self._persist_failure(
                session,
                operation_id=operation_id,
                code=error.code,
                outcome_unknown=error.outcome_unknown,
                now=current_time,
            )
            raise PaymentOperationFailedError(
                error.code,
                outcome_unknown=error.outcome_unknown,
            ) from error

        except Exception as error:  # noqa: BLE001 - the provider outcome may be unknown
            await self._persist_failure(
                session,
                operation_id=operation_id,
                code="provider_unexpected",
                outcome_unknown=True,
                now=current_time,
            )
            raise PaymentOperationFailedError(
                "provider_unexpected",
                outcome_unknown=True,
            ) from error

        expected_status = (
            PaymentAttemptStatus.SUCCEEDED.value
            if operation_type is PaymentOperationType.CAPTURE
            else PaymentAttemptStatus.CANCELED.value
        )
        if snapshot.status != expected_status:
            await self._persist_failure(
                session,
                operation_id=operation_id,
                code="unexpected_provider_status",
                outcome_unknown=True,
                now=current_time,
            )
            raise PaymentOperationFailedError(
                "unexpected_provider_status",
                outcome_unknown=True,
            )

        try:
            applied = await self.payment_service.record_provider_snapshot(
                session,
                attempt_id=attempt.id,
                snapshot=snapshot,
                now=current_time,
            )
            if operation_type is PaymentOperationType.CAPTURE:
                await self.order_lifecycle.confirm_payment(
                    session,
                    order_id=applied.order_id,
                    payment_attempt_id=applied.attempt_id,
                    now=current_time,
                )
            stored = await self.repository.get_for_update(session, operation_id=operation_id)
            if stored is None:
                raise PaymentStateError("Payment operation disappeared")
            stored.status = PaymentOperationStatus.SUCCEEDED.value
            stored.resolved_at = max(current_time, ensure_utc(stored.created_at))
            stored.last_error_code = None
            await session.commit()
            return self._result(stored, replayed=False)
        except (
            InventoryReservationExpiredError,
            InventoryReservationStateError,
            InvalidOrderTransitionError,
            OrderNotFoundError,
            PaymentProviderMismatchError,
            PaymentStateError,
        ) as error:
            await session.rollback()
            await self._persist_failure(
                session,
                operation_id=operation_id,
                code="provider_evidence_processing_failed",
                outcome_unknown=True,
                now=current_time,
            )
            raise PaymentOperationFailedError(
                "provider_evidence_processing_failed",
                outcome_unknown=True,
            ) from error
        except Exception as error:  # noqa: BLE001 - provider success must stay retryable
            await session.rollback()
            await self._persist_failure(
                session,
                operation_id=operation_id,
                code="provider_evidence_processing_failed",
                outcome_unknown=True,
                now=current_time,
            )
            raise PaymentOperationFailedError(
                "provider_evidence_processing_failed",
                outcome_unknown=True,
            ) from error

    async def _latest_attempt_id(self, session: AsyncSession, *, order_id: int) -> int:
        if order_id <= 0:
            raise PaymentStateError("Order payment does not exist")
        payment = await self.payment_repository.get_payment_for_update(
            session,
            order_id=order_id,
        )
        if payment is None:
            raise PaymentStateError("Order payment does not exist")
        attempt = await self.payment_repository.get_latest_attempt_for_update(
            session,
            payment_id=payment.id,
        )
        if attempt is None:
            raise PaymentStateError("Order payment attempt does not exist")
        return attempt.id

    async def _call_provider(
        self,
        operation: PaymentOperation,
        attempt: PaymentAttempt,
    ):
        provider_payment_id = attempt.provider_payment_id
        if provider_payment_id is None:
            raise PaymentStateError("Payment attempt has no provider identity")
        if operation.operation_type == PaymentOperationType.CAPTURE.value:
            return await self.provider.capture_payment(
                provider_payment_id,
                idempotence_key=operation.provider_idempotence_key,
                request_body=b"{}",
            )
        return await self.provider.cancel_payment(
            provider_payment_id,
            idempotence_key=operation.provider_idempotence_key,
        )

    async def _reconcile_operation_from_attempt(
        self,
        session: AsyncSession,
        *,
        operation: PaymentOperation,
        attempt: PaymentAttempt,
        operation_type: PaymentOperationType,
        now: datetime,
    ) -> PaymentOperationResult | None:
        expected_status = (
            PaymentAttemptStatus.SUCCEEDED.value
            if operation_type is PaymentOperationType.CAPTURE
            else PaymentAttemptStatus.CANCELED.value
        )
        if attempt.status == expected_status:
            operation_id = operation.id
            if operation_type is PaymentOperationType.CAPTURE:
                try:
                    await self.order_lifecycle.confirm_payment(
                        session,
                        order_id=attempt.payment.order_id,
                        payment_attempt_id=attempt.id,
                        now=now,
                    )
                except Exception as error:  # noqa: BLE001 - retain an auditable retry
                    await session.rollback()
                    await self._persist_failure(
                        session,
                        operation_id=operation_id,
                        code="provider_evidence_processing_failed",
                        outcome_unknown=True,
                        now=now,
                    )
                    raise PaymentOperationFailedError(
                        "provider_evidence_processing_failed",
                        outcome_unknown=True,
                    ) from error
            operation.status = PaymentOperationStatus.SUCCEEDED.value
            operation.resolved_at = max(now, ensure_utc(operation.created_at))
            operation.last_error_code = None
            await session.commit()
            return self._result(operation, replayed=True)
        if attempt.status in {
            PaymentAttemptStatus.SUCCEEDED.value,
            PaymentAttemptStatus.CANCELED.value,
        }:
            operation.status = PaymentOperationStatus.FAILED.value
            operation.resolved_at = max(now, ensure_utc(operation.created_at))
            operation.last_error_code = "provider_terminal_state"
            await session.commit()
            raise PaymentOperationFailedError(
                "provider_terminal_state",
                outcome_unknown=False,
            )
        return None

    async def _persist_failure(
        self,
        session: AsyncSession,
        *,
        operation_id: int,
        code: str,
        outcome_unknown: bool,
        now: datetime,
    ) -> None:
        operation = await self.repository.get_for_update(session, operation_id=operation_id)
        if operation is None:
            raise PaymentStateError("Payment operation disappeared after provider call")
        if operation.status == PaymentOperationStatus.SUCCEEDED.value:
            await session.commit()
            return
        operation.status = (
            PaymentOperationStatus.UNKNOWN.value
            if outcome_unknown
            else PaymentOperationStatus.FAILED.value
        )
        operation.resolved_at = (
            None
            if outcome_unknown
            else max(
                now,
                ensure_utc(operation.created_at),
            )
        )
        operation.last_error_code = code
        await session.commit()

    @staticmethod
    def _validate_attempt(
        attempt: PaymentAttempt,
        *,
        operation_type: PaymentOperationType,
        now: datetime,
    ) -> None:
        if attempt.capture_mode != PaymentCaptureMode.MANUAL.value:
            raise PaymentOperationConflictError("Payment was not created for manual capture")
        if attempt.status != PaymentAttemptStatus.WAITING_FOR_CAPTURE.value:
            raise PaymentOperationConflictError("Payment is not waiting for capture")
        if attempt.provider_payment_id is None:
            raise PaymentOperationConflictError("Payment has no provider identity")
        if (
            operation_type is PaymentOperationType.CAPTURE
            and attempt.expires_at is not None
            and ensure_utc(attempt.expires_at) <= now
        ):
            raise PaymentOperationConflictError("Payment capture window has expired")

    @staticmethod
    def _validate_replay(
        operation: PaymentOperation,
        *,
        attempt_id: int,
        operation_type: PaymentOperationType,
        client_digest: str,
        request_digest: str,
        actor_user_id: int,
    ) -> None:
        if (
            operation.payment_attempt_id != attempt_id
            or operation.operation_type != operation_type.value
            or operation.client_key_digest_sha256 != client_digest
            or operation.request_sha256 != request_digest
            or operation.actor_user_id != actor_user_id
        ):
            raise PaymentOperationConflictError(
                "Payment operation idempotency key was already used"
            )

    @staticmethod
    def _request_digest(
        attempt: PaymentAttempt,
        operation_type: PaymentOperationType,
    ) -> str:
        value = f"{attempt.id}:{attempt.provider_payment_id}:{operation_type.value}:{{}}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _provider_key(self) -> str:
        value = self.provider_key_factory()
        try:
            parsed = uuid.UUID(value)
        except (AttributeError, TypeError, ValueError) as error:
            raise RuntimeError("Invalid payment operation provider key") from error
        if parsed.version != 4 or str(parsed) != value:
            raise RuntimeError("Payment operation provider key must be UUIDv4")
        return value

    @staticmethod
    def _result(
        operation: PaymentOperation,
        *,
        replayed: bool,
    ) -> PaymentOperationResult:
        attempt = operation.attempt
        if attempt.provider_payment_id is None:
            raise PaymentStateError("Payment operation has no provider identity")
        return PaymentOperationResult(
            operation_id=operation.id,
            payment_attempt_id=attempt.id,
            order_id=attempt.payment.order_id,
            operation=operation.operation_type,
            operation_status=operation.status,
            payment_status=attempt.status,
            provider_payment_id=attempt.provider_payment_id,
            capture_expires_at=attempt.expires_at,
            replayed=replayed,
        )
