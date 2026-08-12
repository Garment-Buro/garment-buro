from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.delivery.canonical import (
    CanonicalCdekRequest,
    CdekCanonicalRequestBuilder,
    CdekRequestValidationError,
)
from app.modules.delivery.crypto import CdekRequestCodec, CdekRequestEncryptionError
from app.modules.delivery.repository import (
    CdekShipmentEvidenceConflictError,
    CdekShipmentRepository,
)
from app.modules.fulfillment.contracts import FulfillmentHandlerError
from app.modules.fulfillment.models import FulfillmentJob, FulfillmentJobKind
from app.modules.fulfillment.repository import FulfillmentRepository
from app.modules.fulfillment.service import PAID_FULFILLMENT_ORDER_STATUSES
from app.modules.orders.models import OrderPaymentStatus


@dataclass(frozen=True, slots=True)
class PreparedCdekShipment:
    order_id: int
    fulfillment_job_id: int
    payment_attempt_id: int
    request: CanonicalCdekRequest


class CdekShipmentHandoffHandler:
    """Atomically turn a paid-order command into a private CDEK shipment request."""

    kind = FulfillmentJobKind.CDEK_ORDER_CREATE

    def __init__(
        self,
        settings: Settings,
        codec: CdekRequestCodec,
        *,
        fulfillment_repository: FulfillmentRepository | None = None,
        shipment_repository: CdekShipmentRepository | None = None,
        builder: CdekCanonicalRequestBuilder | None = None,
    ) -> None:
        self.settings = settings
        self.codec = codec
        self.fulfillment_repository = fulfillment_repository or FulfillmentRepository()
        self.shipment_repository = shipment_repository or CdekShipmentRepository()
        self.builder = builder or CdekCanonicalRequestBuilder(settings)

    async def prepare(
        self,
        session: AsyncSession,
        job: FulfillmentJob,
        *,
        now: datetime,
    ) -> PreparedCdekShipment:
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
        try:
            request = self.builder.build(order)
        except CdekRequestValidationError as error:
            raise FulfillmentHandlerError(error.code, permanent=True) from error
        return PreparedCdekShipment(
            order_id=order.id,
            fulfillment_job_id=job.id,
            payment_attempt_id=attempt.id,
            request=request,
        )

    async def apply(
        self,
        session: AsyncSession,
        job: FulfillmentJob,
        prepared: object,
        *,
        now: datetime,
    ) -> str:
        if job.kind != self.kind.value or not isinstance(prepared, PreparedCdekShipment):
            raise FulfillmentHandlerError("prepared_action_invalid", permanent=True)
        if (
            prepared.order_id != job.order_id
            or prepared.fulfillment_job_id != job.id
            or prepared.payment_attempt_id != job.source_payment_attempt_id
        ):
            raise FulfillmentHandlerError("prepared_order_mismatch", permanent=True)
        try:
            encrypted = self.codec.encrypt(
                prepared.request.body,
                order_id=prepared.order_id,
                request_sha256=prepared.request.sha256,
                schema_version=prepared.request.schema_version,
            )
            shipment = await self.shipment_repository.acquire_prepared(
                session,
                order_id=prepared.order_id,
                source_fulfillment_job_id=prepared.fulfillment_job_id,
                source_payment_attempt_id=prepared.payment_attempt_id,
                client_order_number=prepared.request.client_order_number,
                request_sha256=prepared.request.sha256,
                request_schema_version=prepared.request.schema_version,
                encrypted=encrypted,
                max_attempts=self.settings.cdek_creation_max_attempts,
                available_at=now,
            )
        except CdekRequestEncryptionError as error:
            raise FulfillmentHandlerError(
                "cdek_request_encryption_failed",
                permanent=True,
            ) from error
        except CdekShipmentEvidenceConflictError as error:
            raise FulfillmentHandlerError("cdek_evidence_conflict", permanent=True) from error
        return f"cdek-shipment:{shipment.id}"
