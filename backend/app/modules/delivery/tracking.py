"""Authenticated CDEK reads update the customer lifecycle, never an untrusted webhook body."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.delivery.models import CdekShipment, CdekShipmentEvent
from app.modules.delivery.provider import CdekOrderSnapshot
from app.modules.identity.security import ensure_utc
from app.modules.orders.models import Order
from app.modules.orders.service import OrderLifecycleService
from app.modules.orders.workflow_repository import workflow_for_order

# ACCEPTED means registered electronically, not physical handover.
HANDED_OVER = frozenset(
    {
        "RECEIVED_AT_SHIPMENT_WAREHOUSE",
        "READY_FOR_SHIPMENT_IN_SENDER_CITY",
        "TAKEN_BY_TRANSPORTER_FROM_SENDER_CITY",
        "SENT_TO_TRANSIT_CITY",
        "ACCEPTED_IN_TRANSIT_CITY",
        "ACCEPTED_AT_TRANSIT_WAREHOUSE",
        "SENT_TO_SENDER_CITY",
        "SENT_TO_RECIPIENT_CITY",
        "ACCEPTED_IN_RECIPIENT_CITY",
        "ACCEPTED_AT_RECIPIENT_CITY_WAREHOUSE",
        "ACCEPTED_AT_PICK_UP_POINT",
        "TAKEN_BY_COURIER",
        "DELIVERED",
        "RETURNED_TO_SENDER_CITY_WAREHOUSE",
        "RETURNED_TO_TRANSIT_WAREHOUSE",
        "RETURNED_TO_RECIPIENT_CITY_WAREHOUSE",
        "READY_FOR_SHIPMENT_IN_TRANSIT_CITY",
        "TAKEN_BY_TRANSPORTER_FROM_TRANSIT_CITY",
        "ACCEPTED_IN_SENDER_CITY",
    }
)


async def apply_tracking(
    session: AsyncSession,
    settings: Settings,
    *,
    shipment_id: int,
    snapshot: CdekOrderSnapshot,
    now: datetime,
) -> bool:
    shipment_order_id = await session.scalar(
        select(CdekShipment.order_id).where(CdekShipment.id == shipment_id)
    )
    await session.scalar(select(Order).where(Order.id == shipment_order_id).with_for_update())
    flow = await workflow_for_order(session, shipment_order_id)
    shipment = await session.scalar(
        select(CdekShipment)
        .where(CdekShipment.id == shipment_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if shipment is None or flow is None or shipment.provider_uuid != snapshot.provider_uuid:
        raise ValueError("CDEK shipment identity mismatch")
    if snapshot.client_order_number != shipment.client_order_number:
        raise ValueError("CDEK client order identity mismatch")
    if (
        shipment.provider_cdek_number is not None
        and snapshot.cdek_number != shipment.provider_cdek_number
    ):
        raise ValueError("CDEK tracking number mismatch")
    if snapshot.status_at is None or snapshot.status_code is None:
        raise ValueError("CDEK dated status is required")
    observed_at = ensure_utc(snapshot.status_at)
    if observed_at > ensure_utc(now):
        raise ValueError("CDEK future status")
    if flow.state == "completed":
        return True
    if flow.cdek_status_at is not None and observed_at <= ensure_utc(flow.cdek_status_at):
        return False
    flow.cdek_status, flow.cdek_status_at = snapshot.status_code, observed_at
    shipment.provider_cdek_number = snapshot.cdek_number
    shipment.provider_status_code = snapshot.status_code
    shipment.provider_status_name = snapshot.status_name
    shipment.provider_status_observed_at = now
    session.add(
        CdekShipmentEvent(
            shipment_id=shipment.id,
            event_type="status_observed",
            event_key=f"tracking:{shipment.id}:{observed_at.isoformat()}:{snapshot.status_code}",
            provider_status_code=snapshot.status_code,
            occurred_at=now,
        )
    )
    lifecycle = OrderLifecycleService(settings)
    if snapshot.status_code in HANDED_OVER and flow.state == "production":
        await session.flush()
        await lifecycle.mark_shipped(session, order_id=flow.order_id, actor_user_id=None)
    if snapshot.status_code == "DELIVERED" and flow.state == "shipped":
        await session.flush()
        await lifecycle.mark_completed(session, order_id=flow.order_id, actor_user_id=None)
    elif snapshot.status_code in {"NOT_DELIVERED", "RETURNED", "REMOVED"}:
        flow.attention_code = "cdek_" + snapshot.status_code.lower()
    await session.flush()
    return flow.state == "completed"
