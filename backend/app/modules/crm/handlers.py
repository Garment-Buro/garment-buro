from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.repository import (
    CrmProductionUnitSnapshot,
    CrmProjectEvidenceConflictError,
    CrmProjectRepository,
)
from app.modules.fulfillment.contracts import FulfillmentHandlerError
from app.modules.fulfillment.models import FulfillmentJob, FulfillmentJobKind
from app.modules.fulfillment.repository import FulfillmentRepository
from app.modules.fulfillment.service import PAID_FULFILLMENT_ORDER_STATUSES
from app.modules.identity.security import ensure_utc
from app.modules.orders.models import OrderPaymentStatus


@dataclass(frozen=True, slots=True)
class PreparedCrmOrderProject:
    order_id: int
    fulfillment_job_id: int
    payment_attempt_id: int
    order_version: int
    total_price: Decimal
    currency: str
    payment_succeeded_at: datetime
    units: tuple[CrmProductionUnitSnapshot, ...]


class CrmOrderProjectHandoffHandler:
    """Atomically project a paid order into the PII-free production domain."""

    kind = FulfillmentJobKind.CRM_ORDER_PROJECT

    def __init__(
        self,
        *,
        fulfillment_repository: FulfillmentRepository | None = None,
        project_repository: CrmProjectRepository | None = None,
    ) -> None:
        self.fulfillment_repository = fulfillment_repository or FulfillmentRepository()
        self.project_repository = project_repository or CrmProjectRepository()

    async def prepare(
        self,
        session: AsyncSession,
        job: FulfillmentJob,
        *,
        now: datetime,
    ) -> PreparedCrmOrderProject:
        del now
        if job.kind != self.kind.value:
            raise FulfillmentHandlerError("handler_kind_mismatch", permanent=True)
        order = await self.fulfillment_repository.get_paid_order_with_items_for_update(
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
        attempt = await self.fulfillment_repository.get_succeeded_attempt(
            session,
            order_id=order.id,
            attempt_id=job.source_payment_attempt_id,
        )
        if attempt is None:
            raise FulfillmentHandlerError("payment_evidence_missing", permanent=True)
        payment = await self.fulfillment_repository.get_succeeded_payment(
            session,
            order_id=order.id,
            payment_id=attempt.payment_id,
        )
        if payment is None or payment.succeeded_at is None:
            raise FulfillmentHandlerError("payment_evidence_missing", permanent=True)
        if not order.items:
            raise FulfillmentHandlerError("order_items_missing", permanent=True)

        units = tuple(
            CrmProductionUnitSnapshot(
                order_item_id=item.id,
                product_id_snapshot=item.product_id_snapshot,
                variant_id_snapshot=item.variant_id_snapshot,
                unit_number=unit_number,
            )
            for item in order.items
            for unit_number in range(1, item.quantity + 1)
        )
        if not units:
            raise FulfillmentHandlerError("order_units_missing", permanent=True)
        return PreparedCrmOrderProject(
            order_id=order.id,
            fulfillment_job_id=job.id,
            payment_attempt_id=attempt.id,
            order_version=order.version,
            total_price=order.total_price,
            currency=order.currency,
            payment_succeeded_at=ensure_utc(payment.succeeded_at),
            units=units,
        )

    async def apply(
        self,
        session: AsyncSession,
        job: FulfillmentJob,
        prepared: object,
        *,
        now: datetime,
    ) -> str:
        if job.kind != self.kind.value or not isinstance(prepared, PreparedCrmOrderProject):
            raise FulfillmentHandlerError("prepared_action_invalid", permanent=True)
        if (
            prepared.order_id != job.order_id
            or prepared.fulfillment_job_id != job.id
            or prepared.payment_attempt_id != job.source_payment_attempt_id
        ):
            raise FulfillmentHandlerError("prepared_order_mismatch", permanent=True)
        try:
            project = await self.project_repository.acquire_from_paid_order(
                session,
                order_id=prepared.order_id,
                source_fulfillment_job_id=prepared.fulfillment_job_id,
                source_payment_attempt_id=prepared.payment_attempt_id,
                order_version_snapshot=prepared.order_version,
                total_price_snapshot=prepared.total_price,
                currency=prepared.currency,
                payment_succeeded_at_snapshot=prepared.payment_succeeded_at,
                units=prepared.units,
                now=now,
            )
        except CrmProjectEvidenceConflictError as error:
            raise FulfillmentHandlerError("crm_evidence_conflict", permanent=True) from error
        return f"crm-project:{project.id}"
