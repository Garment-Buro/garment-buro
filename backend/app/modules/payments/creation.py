from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.identity.security import ensure_utc
from app.modules.inventory.service import (
    InventoryReservationExpiredError,
    InventoryReservationStateError,
)
from app.modules.orders.models import Order
from app.modules.orders.service import (
    InvalidOrderTransitionError,
    OrderLifecycleService,
    OrderNotFoundError,
)
from app.modules.payments.models import PaymentAttempt, PaymentAttemptStatus
from app.modules.payments.provider import YooKassaProvider, YooKassaProviderError
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import (
    ProviderPaymentSnapshot,
    YooKassaCreateAmount,
    YooKassaCreateConfirmation,
    YooKassaCreateMetadata,
    YooKassaCreatePaymentMethod,
    YooKassaCreatePaymentRequest,
    YooKassaReceipt,
    YooKassaReceiptCustomer,
    YooKassaReceiptItem,
)
from app.modules.payments.service import (
    PaymentProviderMismatchError,
    PaymentService,
    PaymentStateError,
)


class PaymentCreationDisabledError(RuntimeError):
    pass


class PaymentCreationInProgressError(RuntimeError):
    pass


class PaymentCreationRequestConflictError(RuntimeError):
    pass


class PaymentCreationRetryExpiredError(RuntimeError):
    pass


class PaymentCreationFailedError(RuntimeError):
    def __init__(self, code: str, *, outcome_unknown: bool) -> None:
        super().__init__(f"Payment creation failed: {code}")
        self.code = code
        self.outcome_unknown = outcome_unknown


@dataclass(frozen=True, slots=True)
class PaymentCreationResult:
    attempt_id: int
    order_id: int
    status: str
    provider_payment_id: str | None
    confirmation_url: str | None
    replayed: bool


class PaymentCreationService:
    """Create one YooKassa payment without losing uncertain provider outcomes."""

    def __init__(
        self,
        settings: Settings,
        provider: YooKassaProvider,
        *,
        repository: PaymentRepository | None = None,
        payment_service: PaymentService | None = None,
        order_lifecycle: OrderLifecycleService | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.repository = repository or PaymentRepository()
        self.payment_service = payment_service or PaymentService(
            settings,
            repository=self.repository,
        )
        self.order_lifecycle = order_lifecycle or OrderLifecycleService(settings)

    async def create_attempt(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        now: datetime | None = None,
    ) -> PaymentCreationResult:
        if not self.settings.payment_creation_enabled:
            raise PaymentCreationDisabledError("Target payment creation is disabled")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        attempt = await self.repository.get_attempt_for_update(
            session,
            attempt_id=attempt_id,
        )
        if attempt is None:
            raise PaymentStateError("Payment attempt does not exist")
        if attempt.status == PaymentAttemptStatus.FAILED.value:
            raise PaymentCreationFailedError(
                attempt.last_error_code or "creation_failed",
                outcome_unknown=False,
            )
        if (
            attempt.status == PaymentAttemptStatus.UNKNOWN.value
            and attempt.provider_payment_id is not None
        ):
            return self._result(attempt, replayed=True)
        if attempt.status not in {
            PaymentAttemptStatus.PREPARED.value,
            PaymentAttemptStatus.UNKNOWN.value,
        }:
            if attempt.status == PaymentAttemptStatus.SUCCEEDED.value:
                await self.order_lifecycle.confirm_payment(
                    session,
                    order_id=attempt.payment.order_id,
                    payment_attempt_id=attempt.id,
                    now=current_time,
                )
                await session.commit()
            return self._result(attempt, replayed=True)

        order = await self.repository.get_order_with_items_for_update(
            session,
            order_id=attempt.payment.order_id,
        )
        if order is None:
            raise PaymentStateError("Payment order does not exist")
        request = self.build_request(order=order, attempt=attempt)
        request_body = request.canonical_bytes()
        request_digest = hashlib.sha256(request_body).hexdigest()
        if (
            attempt.provider_request_sha256 is not None
            and attempt.provider_request_sha256 != request_digest
        ):
            raise PaymentCreationRequestConflictError(
                "Persisted payment request no longer matches the immutable provider request"
            )
        if attempt.creation_started_at is not None:
            started_at = ensure_utc(attempt.creation_started_at)
            if current_time - started_at > timedelta(
                seconds=self.settings.payment_creation_retry_window_seconds
            ):
                await self.payment_service.mark_creation_failed(
                    session,
                    attempt_id=attempt.id,
                    error_code="idempotence_window_expired",
                    now=current_time,
                )
                await session.commit()
                raise PaymentCreationRetryExpiredError("YooKassa idempotence replay window expired")
            if (
                attempt.status == PaymentAttemptStatus.PREPARED.value
                and attempt.creation_last_attempt_at is not None
                and current_time - ensure_utc(attempt.creation_last_attempt_at)
                < timedelta(seconds=self.settings.payment_creation_processing_timeout_seconds)
            ):
                raise PaymentCreationInProgressError(
                    "Payment creation request is already in progress"
                )

        attempt.provider_request_sha256 = request_digest
        attempt.creation_started_at = attempt.creation_started_at or current_time
        attempt.creation_last_attempt_at = current_time
        attempt.creation_attempts_count += 1
        attempt.last_error_code = None
        idempotence_key = attempt.provider_idempotence_key
        await session.commit()

        try:
            snapshot = await self.provider.create_payment(
                idempotence_key=idempotence_key,
                request_body=request_body,
            )
        except YooKassaProviderError as error:
            result = await self._persist_provider_error(
                session,
                attempt_id=attempt_id,
                code=error.code,
                outcome_unknown=error.outcome_unknown,
                now=current_time,
            )
            if result is not None:
                return result
            raise PaymentCreationFailedError(
                error.code,
                outcome_unknown=error.outcome_unknown,
            ) from error
        except Exception as error:  # noqa: BLE001 - persist unknown outcome before surfacing
            result = await self._persist_provider_error(
                session,
                attempt_id=attempt_id,
                code="provider_unexpected",
                outcome_unknown=True,
                now=current_time,
            )
            if result is not None:
                return result
            raise PaymentCreationFailedError(
                "provider_unexpected",
                outcome_unknown=True,
            ) from error

        try:
            applied = await self.payment_service.record_provider_snapshot(
                session,
                attempt_id=attempt_id,
                snapshot=snapshot,
                now=current_time,
            )
            if snapshot.status == PaymentAttemptStatus.SUCCEEDED.value:
                await self.order_lifecycle.confirm_payment(
                    session,
                    order_id=applied.order_id,
                    payment_attempt_id=applied.attempt_id,
                    now=current_time,
                )
            stored = await session.get(PaymentAttempt, applied.attempt_id)
            if stored is None:
                raise PaymentStateError("Payment attempt disappeared after provider creation")
            await session.commit()
            return self._result(stored, replayed=False)
        except (PaymentProviderMismatchError, PaymentStateError) as error:
            await session.rollback()
            result = await self._persist_provider_error(
                session,
                attempt_id=attempt_id,
                code="provider_evidence_mismatch",
                outcome_unknown=True,
                now=current_time,
            )
            if result is not None:
                return result
            raise PaymentCreationFailedError(
                "provider_evidence_mismatch",
                outcome_unknown=True,
            ) from error
        except (
            InventoryReservationExpiredError,
            InventoryReservationStateError,
            InvalidOrderTransitionError,
            OrderNotFoundError,
        ) as error:
            await session.rollback()
            result = await self._persist_provider_error(
                session,
                attempt_id=attempt_id,
                code="paid_order_transition_failed",
                outcome_unknown=True,
                now=current_time,
                snapshot=snapshot,
            )
            if result is not None:
                return result
            raise PaymentCreationFailedError(
                "paid_order_transition_failed",
                outcome_unknown=True,
            ) from error
        except Exception as error:  # noqa: BLE001 - preserve an accepted provider outcome
            await session.rollback()
            result = await self._persist_provider_error(
                session,
                attempt_id=attempt_id,
                code="processing_unexpected",
                outcome_unknown=True,
                now=current_time,
                snapshot=snapshot,
            )
            if result is not None:
                return result
            raise PaymentCreationFailedError(
                "processing_unexpected",
                outcome_unknown=True,
            ) from error

    def build_request(
        self,
        *,
        order: Order,
        attempt: PaymentAttempt,
    ) -> YooKassaCreatePaymentRequest:
        if order.id is None or order.id != attempt.payment.order_id:
            raise PaymentStateError("Payment attempt does not match its order")
        if not order.email_normalized:
            raise PaymentStateError("Order email is required for a fiscal receipt")
        if not order.items:
            raise PaymentStateError("Order has no immutable receipt items")
        if sum((item.line_total for item in order.items), Decimal("0.00")) != order.items_subtotal:
            raise PaymentStateError("Order item snapshots do not match the stored subtotal")

        items: list[YooKassaReceiptItem] = []
        for item in order.items:
            if item.unit_price <= 0:
                raise PaymentStateError("Zero-price order items are not supported in receipts")
            items.append(
                YooKassaReceiptItem(
                    description=self._receipt_description(item.title_snapshot),
                    quantity=Decimal(item.quantity),
                    amount=YooKassaCreateAmount(
                        value=item.unit_price,
                        currency=order.currency,
                    ),
                    vat_code=self._required_int(
                        self.settings.yookassa_receipt_product_vat_code,
                        "product VAT code",
                    ),
                    payment_mode=self.settings.yookassa_receipt_product_payment_mode,
                    payment_subject=self.settings.yookassa_receipt_product_subject,
                )
            )
        if order.delivery_price > 0:
            items.append(
                YooKassaReceiptItem(
                    description="Доставка",
                    quantity=Decimal("1.00"),
                    amount=YooKassaCreateAmount(
                        value=order.delivery_price,
                        currency=order.currency,
                    ),
                    vat_code=self._required_int(
                        self.settings.yookassa_receipt_delivery_vat_code,
                        "delivery VAT code",
                    ),
                    payment_mode=self.settings.yookassa_receipt_delivery_payment_mode,
                    payment_subject=self.settings.yookassa_receipt_delivery_subject,
                )
            )
        return YooKassaCreatePaymentRequest(
            amount=YooKassaCreateAmount(value=order.total_price, currency=order.currency),
            payment_method_data=YooKassaCreatePaymentMethod(type=attempt.payment_method),
            confirmation=YooKassaCreateConfirmation(
                return_url=f"{self.settings.public_base_url.rstrip('/')}/order/{order.id}"
            ),
            description=f"Заказ №{order.id}",
            metadata=YooKassaCreateMetadata(order_id=order.id),
            receipt=YooKassaReceipt(
                customer=YooKassaReceiptCustomer(email=order.email_normalized),
                items=items,
                tax_system_code=self.settings.yookassa_receipt_tax_system_code,
            ),
        )

    async def _persist_provider_error(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        code: str,
        outcome_unknown: bool,
        now: datetime,
        snapshot: ProviderPaymentSnapshot | None = None,
    ) -> PaymentCreationResult | None:
        attempt = await self.repository.get_attempt_for_update(
            session,
            attempt_id=attempt_id,
        )
        if attempt is None:
            raise PaymentStateError("Payment attempt disappeared after provider call")
        if attempt.status not in {
            PaymentAttemptStatus.PREPARED.value,
            PaymentAttemptStatus.UNKNOWN.value,
        }:
            await session.commit()
            return self._result(attempt, replayed=True)
        if snapshot is not None:
            await self.payment_service.remember_unknown_provider_identity(
                session,
                attempt_id=attempt_id,
                snapshot=snapshot,
                error_code=code,
                now=now,
            )
        elif outcome_unknown:
            await self.payment_service.mark_creation_unknown(
                session,
                attempt_id=attempt_id,
                error_code=code,
                now=now,
            )
        else:
            await self.payment_service.mark_creation_failed(
                session,
                attempt_id=attempt_id,
                error_code=code,
                now=now,
            )
        await session.commit()
        return None

    @staticmethod
    def _receipt_description(value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise PaymentStateError("Receipt item title must not be blank")
        return normalized[:128]

    @staticmethod
    def _required_int(value: int | None, label: str) -> int:
        if value is None:
            raise PaymentStateError(f"YooKassa {label} is not configured")
        return value

    @staticmethod
    def _result(attempt: PaymentAttempt, *, replayed: bool) -> PaymentCreationResult:
        return PaymentCreationResult(
            attempt_id=attempt.id,
            order_id=attempt.payment.order_id,
            status=attempt.status,
            provider_payment_id=attempt.provider_payment_id,
            confirmation_url=attempt.confirmation_url,
            replayed=replayed,
        )
