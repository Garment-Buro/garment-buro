from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.delivery.constants import CDEK_DELIVERY_METHODS
from app.modules.fulfillment.models import FulfillmentJob, FulfillmentJobKind
from app.modules.fulfillment.repository import FulfillmentRepository
from app.modules.identity.security import ensure_utc
from app.modules.orders.models import Order, OrderPaymentStatus, OrderStatus

PAID_FULFILLMENT_ORDER_STATUSES = {
    OrderStatus.PROCESSING.value,
    OrderStatus.SHIPPED.value,
    OrderStatus.COMPLETED.value,
}


class FulfillmentStateError(ValueError):
    pass


class FulfillmentOutboxService:
    """Schedule PII-free post-payment commands in the payment transaction."""

    def __init__(
        self,
        settings: Settings,
        *,
        repository: FulfillmentRepository | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or FulfillmentRepository()

    async def schedule_paid_order(
        self,
        session: AsyncSession,
        *,
        order: Order,
        payment_attempt_id: int | None,
        now: datetime | None = None,
    ) -> list[FulfillmentJob]:
        if not self.settings.fulfillment_outbox_enabled:
            return []
        if order.id is None or payment_attempt_id is None or payment_attempt_id <= 0:
            raise FulfillmentStateError("Paid fulfillment requires durable payment evidence")
        if (
            order.payment_status != OrderPaymentStatus.PAID.value
            or order.status not in PAID_FULFILLMENT_ORDER_STATUSES
        ):
            raise FulfillmentStateError("Order is not in a paid fulfillment state")
        attempt = await self.repository.get_succeeded_attempt(
            session,
            order_id=order.id,
            attempt_id=payment_attempt_id,
        )
        if attempt is None:
            raise FulfillmentStateError("Successful payment attempt evidence is missing")

        current_time = ensure_utc(now or datetime.now(timezone.utc))
        jobs = []
        for kind in self._job_kinds(order):
            jobs.append(
                await self.repository.enqueue(
                    session,
                    order_id=order.id,
                    source_payment_attempt_id=payment_attempt_id,
                    kind=kind,
                    max_attempts=self.settings.fulfillment_max_attempts,
                    available_at=current_time,
                )
            )
        await session.flush()
        return jobs

    async def seed_paid_orders(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> int:
        if not self.settings.fulfillment_outbox_enabled:
            return 0
        if not 1 <= limit <= 1_000:
            raise ValueError("Fulfillment seed limit must be between 1 and 1000")
        evidence = await self.repository.list_paid_order_evidence_for_update(
            session,
            limit=limit,
        )
        inserted = 0
        for order, attempt in evidence:
            existing_ids = {
                job.id
                for job in await self.repository.list_order_jobs(
                    session,
                    order_id=order.id,
                )
            }
            jobs = await self.schedule_paid_order(
                session,
                order=order,
                payment_attempt_id=attempt.id,
                now=now,
            )
            inserted += sum(job.id not in existing_ids for job in jobs)
        return inserted

    @staticmethod
    def _job_kinds(order: Order) -> tuple[FulfillmentJobKind, ...]:
        kinds = [FulfillmentJobKind.CRM_ORDER_PROJECT]
        if order.email_normalized:
            kinds.append(FulfillmentJobKind.CUSTOMER_PAYMENT_EMAIL)
        if order.delivery_method in CDEK_DELIVERY_METHODS:
            kinds.append(FulfillmentJobKind.CDEK_ORDER_CREATE)
        return tuple(kinds)
