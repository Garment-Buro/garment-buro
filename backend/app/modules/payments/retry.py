from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.identity.security import ensure_utc
from app.modules.inventory.service import (
    InventoryReservationExpiredError,
    InventoryReservationService,
    InventoryReservationStateError,
)
from app.modules.orders.models import OrderGuestAccess
from app.modules.orders.repository import TargetOrderReadRepository
from app.modules.orders.security import (
    InvalidOrderGuestAccessTokenError,
    digest_order_guest_access_token,
)
from app.modules.payments.creation import PaymentCreationFailedError, PaymentCreationService
from app.modules.payments.models import PaymentAttemptStatus, PaymentStatus
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.security import digest_payment_attempt_key
from app.modules.payments.service import PaymentService

RETRYABLE_TERMINAL_ATTEMPT_STATUSES = {
    PaymentAttemptStatus.FAILED.value,
    PaymentAttemptStatus.CANCELED.value,
}


class PaymentRetryDisabledError(RuntimeError):
    pass


class PaymentRetryActorError(ValueError):
    pass


class PaymentRetryNotFoundError(LookupError):
    pass


class PaymentRetryStateError(ValueError):
    pass


class PaymentRetryError(RuntimeError):
    def __init__(
        self,
        *,
        order_id: int,
        payment_attempt_id: int,
        code: str,
        outcome_unknown: bool,
    ) -> None:
        super().__init__(f"Payment retry failed: {code}")
        self.order_id = order_id
        self.payment_attempt_id = payment_attempt_id
        self.code = code
        self.outcome_unknown = outcome_unknown


@dataclass(frozen=True, slots=True)
class PaymentRetryResult:
    order_id: int
    payment_attempt_id: int
    payment_attempt_number: int
    payment_attempt_status: str
    replayed: bool
    payment_url: str | None


class PaymentRetryService:
    """Create one later payment attempt for an authorized retained target order."""

    def __init__(
        self,
        settings: Settings,
        payment_creation_service: PaymentCreationService,
        *,
        payment_service: PaymentService | None = None,
        payment_repository: PaymentRepository | None = None,
        inventory_service: InventoryReservationService | None = None,
        order_repository: TargetOrderReadRepository | None = None,
    ) -> None:
        self.settings = settings
        self.payment_creation_service = payment_creation_service
        self.payment_service = payment_service or PaymentService(settings)
        self.payment_repository = payment_repository or self.payment_service.repository
        self.inventory_service = inventory_service or InventoryReservationService(settings)
        self.order_repository = order_repository or TargetOrderReadRepository()

    async def retry(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        idempotency_key: str,
        user_id: int | None = None,
        guest_access_token: str | None = None,
        now: datetime | None = None,
    ) -> PaymentRetryResult:
        if not self.settings.checkout_v2_enabled or not self.settings.payment_creation_enabled:
            raise PaymentRetryDisabledError("Target payment retry is disabled")
        if order_id <= 0:
            raise PaymentRetryNotFoundError("Target order was not found")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        attempt_key_digest = digest_payment_attempt_key(idempotency_key)
        self._validate_actor(user_id=user_id, guest_access_token=guest_access_token)

        try:
            existing = await self.payment_repository.get_attempt_by_client_digest(
                session,
                client_key_digest_sha256=attempt_key_digest,
                for_update=True,
            )
            order = await self.payment_repository.get_order_for_update(
                session,
                order_id=order_id,
            )
            if order is None or await self.payment_repository.is_legacy_import(
                session,
                order_id=order_id,
            ):
                raise PaymentRetryNotFoundError("Target order was not found")
            await self._authorize(
                session,
                order_id=order_id,
                order_user_id=order.user_id,
                user_id=user_id,
                guest_access_token=guest_access_token,
                now=current_time,
            )

            if existing is None:
                appeared = await self.payment_repository.get_attempt_by_client_digest(
                    session,
                    client_key_digest_sha256=attempt_key_digest,
                    for_update=False,
                )
                if appeared is not None:
                    await session.rollback()
                    return await self.retry(
                        session,
                        order_id=order_id,
                        idempotency_key=idempotency_key,
                        user_id=user_id,
                        guest_access_token=guest_access_token,
                        now=current_time,
                    )
                await self._validate_new_attempt(
                    session,
                    order_id=order_id,
                    now=current_time,
                )

            prepared = await self.payment_service.prepare_attempt(
                session,
                order_id=order_id,
                client_attempt_key=idempotency_key,
            )
            await session.commit()

            try:
                created = await self.payment_creation_service.create_attempt(
                    session,
                    attempt_id=prepared.attempt_id,
                    now=current_time,
                )
            except PaymentCreationFailedError as error:
                await session.rollback()
                raise PaymentRetryError(
                    order_id=order_id,
                    payment_attempt_id=prepared.attempt_id,
                    code=error.code,
                    outcome_unknown=error.outcome_unknown,
                ) from error
            await session.commit()
            return PaymentRetryResult(
                order_id=order_id,
                payment_attempt_id=created.attempt_id,
                payment_attempt_number=prepared.attempt_number,
                payment_attempt_status=created.status,
                replayed=prepared.replayed or created.replayed,
                payment_url=created.confirmation_url,
            )
        except PaymentRetryError:
            raise
        except Exception:
            await session.rollback()
            raise

    @staticmethod
    def _validate_actor(*, user_id: int | None, guest_access_token: str | None) -> None:
        if user_id is not None and user_id <= 0:
            raise PaymentRetryActorError("Authenticated payment retry user ID must be positive")
        if user_id is None and guest_access_token is None:
            raise PaymentRetryNotFoundError("Target order was not found")
        if user_id is not None and guest_access_token is not None:
            raise PaymentRetryActorError(
                "Authenticated payment retry must not receive a guest access token"
            )

    async def _authorize(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        order_user_id: int | None,
        user_id: int | None,
        guest_access_token: str | None,
        now: datetime,
    ) -> None:
        if user_id is not None:
            if order_user_id != user_id:
                raise PaymentRetryNotFoundError("Target order was not found")
            return
        if guest_access_token is None or order_user_id is not None:
            raise PaymentRetryNotFoundError("Target order was not found")
        try:
            token_digest = digest_order_guest_access_token(guest_access_token)
        except InvalidOrderGuestAccessTokenError as error:
            raise PaymentRetryNotFoundError("Target order was not found") from error
        access = await self.order_repository.get_guest_access_for_update(
            session,
            order_id=order_id,
        )
        if not self._valid_guest_access(access, token_digest=token_digest, now=now):
            raise PaymentRetryNotFoundError("Target order was not found")

    async def _validate_new_attempt(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        now: datetime,
    ) -> None:
        payment = await self.payment_repository.get_payment_for_update(
            session,
            order_id=order_id,
        )
        if payment is None or payment.status == PaymentStatus.SUCCEEDED.value:
            raise PaymentRetryStateError("Order has no retryable payment")
        latest = await self.payment_repository.get_latest_attempt_for_update(
            session,
            payment_id=payment.id,
        )
        if latest is None or latest.status not in RETRYABLE_TERMINAL_ATTEMPT_STATUSES:
            raise PaymentRetryStateError("Latest payment attempt is not retryable")
        if latest.attempt_number >= self.settings.payment_max_attempts_per_order:
            raise PaymentRetryStateError("Order payment attempt limit is exhausted")
        try:
            await self.inventory_service.refresh_active_order(
                session,
                order_id=order_id,
                now=now,
            )
        except (InventoryReservationExpiredError, InventoryReservationStateError) as error:
            raise PaymentRetryStateError("Order inventory reservation is not retryable") from error

    @staticmethod
    def _valid_guest_access(
        access: OrderGuestAccess | None,
        *,
        token_digest: str,
        now: datetime,
    ) -> bool:
        return bool(
            access is not None
            and access.revoked_at is None
            and ensure_utc(access.expires_at) > now
            and secrets.compare_digest(access.token_digest_sha256, token_digest)
        )
