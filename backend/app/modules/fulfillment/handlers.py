from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fulfillment.contracts import FulfillmentHandlerError
from app.modules.fulfillment.models import FulfillmentJob, FulfillmentJobKind
from app.modules.fulfillment.repository import FulfillmentRepository
from app.modules.fulfillment.service import PAID_FULFILLMENT_ORDER_STATUSES
from app.modules.notifications.service import NotificationOutboxService
from app.modules.orders.models import OrderPaymentStatus


@dataclass(frozen=True, slots=True)
class PreparedOrderPaymentEmail:
    recipient: str
    order_id: int
    first_name: str | None
    items: tuple[dict[str, object], ...]
    items_subtotal: str
    delivery_price: str
    total_price: str
    currency: str


class OrderPaymentEmailHandler:
    kind = FulfillmentJobKind.CUSTOMER_PAYMENT_EMAIL

    def __init__(
        self,
        notification_service: NotificationOutboxService,
        *,
        repository: FulfillmentRepository | None = None,
    ) -> None:
        self.notification_service = notification_service
        self.repository = repository or FulfillmentRepository()

    async def prepare(
        self,
        session: AsyncSession,
        job: FulfillmentJob,
        *,
        now: datetime,
    ) -> PreparedOrderPaymentEmail:
        del now
        if job.kind != self.kind.value:
            raise FulfillmentHandlerError("handler_kind_mismatch", permanent=True)
        order = await self.repository.get_paid_order_with_items_for_update(
            session,
            order_id=job.order_id,
        )
        if order is None:
            raise FulfillmentHandlerError("order_missing", permanent=True)
        if (
            order.payment_status != OrderPaymentStatus.PAID.value
            or order.status not in PAID_FULFILLMENT_ORDER_STATUSES
        ):
            raise FulfillmentHandlerError("order_not_paid", permanent=True)
        if not order.email_normalized:
            raise FulfillmentHandlerError("recipient_missing", permanent=True)
        attempt = await self.repository.get_succeeded_attempt(
            session,
            order_id=order.id,
            attempt_id=job.source_payment_attempt_id,
        )
        if attempt is None:
            raise FulfillmentHandlerError("payment_evidence_missing", permanent=True)
        if not order.items:
            raise FulfillmentHandlerError("order_items_missing", permanent=True)

        return PreparedOrderPaymentEmail(
            recipient=order.email_normalized,
            order_id=order.id,
            first_name=order.first_name,
            items=tuple(
                {
                    "title": item.title_snapshot,
                    "size": item.size_snapshot,
                    "color": item.color_snapshot,
                    "quantity": item.quantity,
                    "unit_price": self._money(item.unit_price),
                    "line_total": self._money(item.line_total),
                }
                for item in order.items
            ),
            items_subtotal=self._money(order.items_subtotal),
            delivery_price=self._money(order.delivery_price),
            total_price=self._money(order.total_price),
            currency=order.currency,
        )

    async def apply(
        self,
        session: AsyncSession,
        job: FulfillmentJob,
        prepared: object,
        *,
        now: datetime,
    ) -> str:
        if job.kind != self.kind.value or not isinstance(
            prepared,
            PreparedOrderPaymentEmail,
        ):
            raise FulfillmentHandlerError("prepared_action_invalid", permanent=True)
        if prepared.order_id != job.order_id:
            raise FulfillmentHandlerError("prepared_order_mismatch", permanent=True)
        notification = await self.notification_service.enqueue_order_payment_confirmed(
            session,
            recipient=prepared.recipient,
            order_id=prepared.order_id,
            first_name=prepared.first_name,
            items=list(prepared.items),
            items_subtotal=prepared.items_subtotal,
            delivery_price=prepared.delivery_price,
            total_price=prepared.total_price,
            currency=prepared.currency,
            now=now,
        )
        return f"notification:{notification.id}"

    @staticmethod
    def _money(value: Decimal) -> str:
        return f"{value:.2f}"
