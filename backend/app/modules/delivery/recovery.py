"""Resolve ambiguous shipment creation by verified GET; never repeat the POST."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.delivery.models import CdekShipment, CdekShipmentAttempt
from app.modules.delivery.provider import CdekProvider
from app.modules.delivery.repository import CdekShipmentRepository
from app.modules.orders.models import Order
from app.modules.orders.workflow import OrderWorkflowConflict, authorize_moderator
from app.modules.orders.workflow_models import OrderWorkflowEvent
from app.modules.orders.workflow_repository import enqueue, workflow_for_order


async def recover_shipment(
    session: AsyncSession,
    provider: CdekProvider,
    *,
    order_id: int,
    expected_version: int,
    provider_uuid: str,
    actor_id: int,
) -> None:
    await authorize_moderator(session, actor_id)
    snapshot = await provider.get_order(provider_uuid)
    await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    flow = await workflow_for_order(session, order_id)
    shipment = await session.scalar(
        select(CdekShipment)
        .where(CdekShipment.order_id == order_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if flow is None or shipment is None or flow.version != expected_version:
        raise OrderWorkflowConflict("Reload the managed order and shipment")
    if shipment.status != "unknown" or shipment.provider_uuid not in {None, provider_uuid}:
        raise OrderWorkflowConflict("Only the same ambiguous shipment can be recovered")
    if (
        snapshot.provider_uuid != provider_uuid
        or snapshot.client_order_number != shipment.client_order_number
    ):
        raise OrderWorkflowConflict("CDEK response belongs to another order")
    if snapshot.cdek_number is None:
        raise OrderWorkflowConflict("CDEK has not assigned a tracking number yet")
    attempt = await session.scalar(
        select(CdekShipmentAttempt)
        .where(
            CdekShipmentAttempt.shipment_id == shipment.id,
            CdekShipmentAttempt.attempt_number == shipment.attempts_count,
        )
        .with_for_update()
    )
    if attempt is None or attempt.status != "unknown":
        raise OrderWorkflowConflict("Ambiguous creation attempt evidence is required")
    now = datetime.now(timezone.utc)
    await CdekShipmentRepository().mark_created(
        session,
        shipment,
        attempt,
        provider_uuid=provider_uuid,
        cdek_number=snapshot.cdek_number,
        status_code=snapshot.status_code,
        status_name=snapshot.status_name,
        now=now,
    )
    await enqueue(session, flow, "track_delivery", shipment.id, now)
    flow.version += 1
    session.add(
        OrderWorkflowEvent(
            workflow_id=flow.id,
            version=flow.version,
            state=flow.state,
            reason="ops.recovered_cdek_identity",
            actor_user_id=actor_id,
        )
    )
    await session.flush()
