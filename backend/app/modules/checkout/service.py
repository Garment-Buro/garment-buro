from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.checkout.schemas import CheckoutResult
from app.modules.checkout.security import derive_checkout_payment_attempt_key
from app.modules.orders.models import Order
from app.modules.orders.schemas import OrderCreationCommand
from app.modules.orders.security import normalize_order_idempotency_key
from app.modules.orders.service import OrderCreationService
from app.modules.payments.creation import (
    PaymentCreationFailedError,
    PaymentCreationService,
)
from app.modules.payments.service import PaymentService, PreparedPaymentAttempt

SUPPORTED_CHECKOUT_PAYMENT_METHODS = {"card", "qr"}


class PaymentAttemptPreparer(Protocol):
    async def prepare_attempt(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        client_attempt_key: str,
    ) -> PreparedPaymentAttempt: ...


class CheckoutDisabledError(RuntimeError):
    pass


class CheckoutActorError(ValueError):
    pass


class CheckoutPaymentMethodError(ValueError):
    pass


class CheckoutReceiptError(ValueError):
    pass


class CheckoutPaymentError(RuntimeError):
    def __init__(
        self,
        *,
        order_id: int,
        payment_attempt_id: int,
        code: str,
        outcome_unknown: bool,
    ) -> None:
        super().__init__(f"Checkout payment failed: {code}")
        self.order_id = order_id
        self.payment_attempt_id = payment_attempt_id
        self.code = code
        self.outcome_unknown = outcome_unknown


class CheckoutService:
    """Atomically prepare a replayable checkout before provider network access."""

    def __init__(
        self,
        settings: Settings,
        payment_creation_service: PaymentCreationService,
        *,
        order_creation_service: OrderCreationService | None = None,
        payment_service: PaymentAttemptPreparer | None = None,
    ) -> None:
        self.settings = settings
        self.order_creation_service = order_creation_service or OrderCreationService(settings)
        self.payment_service = payment_service or PaymentService(settings)
        self.payment_creation_service = payment_creation_service

    async def checkout(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        command: OrderCreationCommand,
        user_id: int | None = None,
        guest_access_token: str | None = None,
        now: datetime | None = None,
    ) -> CheckoutResult:
        if not self.settings.checkout_v2_enabled:
            raise CheckoutDisabledError("Target checkout is disabled")
        normalized_key = normalize_order_idempotency_key(idempotency_key)
        self._validate_actor(user_id=user_id, guest_access_token=guest_access_token)
        if command.payment_method not in SUPPORTED_CHECKOUT_PAYMENT_METHODS:
            raise CheckoutPaymentMethodError("Checkout payment method is not supported")

        try:
            order = await self.order_creation_service.create(
                session,
                idempotency_key=normalized_key,
                command=command,
                user_id=user_id,
                guest_access_token=guest_access_token,
                now=now,
            )
            stored_order = await self.order_creation_service.repository.get_order(
                session,
                order.order_id,
            )
            if stored_order is None:
                raise RuntimeError("Prepared checkout order disappeared")
            self._validate_receipt_snapshot(stored_order)

            prepared = await self.payment_service.prepare_attempt(
                session,
                order_id=order.order_id,
                client_attempt_key=derive_checkout_payment_attempt_key(normalized_key),
            )
            await session.commit()

            try:
                payment = await self.payment_creation_service.create_attempt(
                    session,
                    attempt_id=prepared.attempt_id,
                    now=now,
                )
            except PaymentCreationFailedError as error:
                await session.rollback()
                raise CheckoutPaymentError(
                    order_id=order.order_id,
                    payment_attempt_id=prepared.attempt_id,
                    code=error.code,
                    outcome_unknown=error.outcome_unknown,
                ) from error
            current_order = await self.order_creation_service.repository.get_order(
                session,
                order.order_id,
            )
            if current_order is None:
                raise RuntimeError("Checkout order disappeared after payment creation")
            await session.commit()
            return CheckoutResult(
                order_id=order.order_id,
                order_replayed=order.replayed,
                order_status=current_order.status,
                order_payment_status=current_order.payment_status,
                total_price=current_order.total_price,
                currency=current_order.currency,
                payment_attempt_id=payment.attempt_id,
                payment_attempt_number=prepared.attempt_number,
                payment_attempt_status=payment.status,
                payment_replayed=prepared.replayed or payment.replayed,
                payment_url=payment.confirmation_url,
            )
        except CheckoutPaymentError:
            raise
        except Exception:
            await session.rollback()
            raise

    @staticmethod
    def _validate_actor(*, user_id: int | None, guest_access_token: str | None) -> None:
        if user_id is not None and user_id <= 0:
            raise CheckoutActorError("Authenticated checkout user ID must be positive")
        if user_id is None and guest_access_token is None:
            raise CheckoutActorError("Guest checkout requires an access token")
        if user_id is not None and guest_access_token is not None:
            raise CheckoutActorError("Authenticated checkout must not receive a guest access token")

    @staticmethod
    def _validate_receipt_snapshot(order: Order) -> None:
        if order.total_price <= 0:
            raise CheckoutReceiptError("Paid checkout total must be positive")
        if not order.email_normalized:
            raise CheckoutReceiptError("Paid checkout requires a receipt email")
        if not order.items or any(item.unit_price <= 0 for item in order.items):
            raise CheckoutReceiptError(
                "Paid checkout receipt items must have positive stored prices"
            )
