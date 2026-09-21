"""Atomic administrator decisions use the same order -> project -> unit lock order as the floor."""

from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import select

from app.modules.crm.models import CrmOrderProject, CrmProductionUnit, CrmProductionUnitStatus
from app.modules.crm.production_service import CrmProductionService
from app.modules.orders.models import Order
from app.modules.production.inbox_models import TicketMessage
from app.modules.production.inbox_service import AdminInboxConflictError
from app.modules.production.models import (
    ProductionBag,
    ProductionEvent,
    ProductionSpecification,
    ProductionWorkItem,
)
from app.modules.production.schemas import STAGE_LABELS
from app.modules.production.ticket_service import TicketService


def targets(bag, work, spec, unit):
    if not bag or not work or not work.issue or not unit:
        return []
    # A packed/completed garment can be unblocked, but cannot silently undo final CRM status.
    result = ["resume"]
    if not spec or bag.state == "inbox" or unit.status in {"completed", "cancelled"}:
        return result
    if bag.flow_version == 1:
        return result + spec.specification["route"][: work.stage_index + 1]
    lanes = ["cut", "waiting_dtf", "kit", "workshop", "packing"]
    if work.lane not in lanes:
        return result
    reached = lanes.index(work.lane)
    result += [
        lane for lane in ["cut", "kit", "workshop", "packing"] if lanes.index(lane) <= reached
    ]
    if spec.specification["print_file_ids"] and reached >= 1:
        result.append("dtf")
    return result


async def routing_options(session, ticket):
    bag = await session.scalar(
        select(ProductionBag).where(ProductionBag.project_id == ticket.project_id)
    )
    work = await session.scalar(
        select(ProductionWorkItem).where(ProductionWorkItem.unit_id == ticket.production_unit_id)
    )
    if not work or work.problem_inbox_item_id != ticket.id:
        return []
    spec = (
        await session.get(ProductionSpecification, work.specification_id)
        if work.specification_id
        else None
    )
    unit = await session.get(CrmProductionUnit, work.unit_id)
    return [
        {
            "value": value,
            "label": "Продолжить текущий этап" if value == "resume" else STAGE_LABELS[value],
        }
        for value in targets(bag, work, spec, unit)
    ]


async def route_ticket(session, ticket_id, actor, payload):
    service = TicketService()
    ticket = await service.item(session, ticket_id)
    if ticket.kind != "production_problem" or not ticket.order_id or not ticket.project_id:
        raise AdminInboxConflictError("Тикет не связан с изделием на производстве")
    order = await session.scalar(select(Order).where(Order.id == ticket.order_id).with_for_update())
    project = await session.scalar(
        select(CrmOrderProject).where(CrmOrderProject.id == ticket.project_id).with_for_update()
    )
    unit = await session.scalar(
        select(CrmProductionUnit)
        .where(CrmProductionUnit.id == ticket.production_unit_id)
        .with_for_update()
    )
    bag = await session.scalar(
        select(ProductionBag).where(ProductionBag.project_id == ticket.project_id).with_for_update()
    )
    work = await session.scalar(
        select(ProductionWorkItem)
        .where(ProductionWorkItem.unit_id == ticket.production_unit_id)
        .with_for_update()
    )
    ticket = await service.item(session, ticket_id, lock=True)
    if ticket.version != payload.expected_version:
        raise AdminInboxConflictError("Тикет изменился. Обновите карточку")
    if (
        not order
        or order.status != "processing"
        or (not order.is_demo and order.payment_status != "paid")
        or not project
        or project.status in {"cancelled", "on_hold"}
        or not work
        or work.problem_inbox_item_id != ticket.id
        or not work.issue
        or ticket.status in {"resolved", "closed"}
    ):
        raise AdminInboxConflictError("Изделие недоступно для передачи или проблема уже решена")
    spec = (
        await session.get(ProductionSpecification, work.specification_id)
        if work.specification_id
        else None
    )
    if payload.target not in targets(bag, work, spec, unit):
        raise AdminInboxConflictError("Нельзя пропускать этапы или изменять завершённое изделие")
    previous_lane = work.lane
    if payload.target != "resume":
        route = spec.specification["route"]
        if bag.flow_version == 1:
            work.stage_index = route.index(payload.target)
            if payload.target in {"cut", "application"}:
                work.dtf_ready = work.dtf_inserted = False
        else:
            work.lane = "waiting_dtf" if payload.target == "dtf" else payload.target
            if payload.target in {"cut", "dtf", "kit"}:
                work.component_checks = {}
            if payload.target in {"cut", "dtf"}:
                work.dtf_ready = work.dtf_inserted = False
            if payload.target == "cut":
                work.stage_index = 0
            elif payload.target == "packing":
                work.stage_index = route.index("packing")
            else:
                work.stage_index = route.index("cut") + 1 if "cut" in route else 0
        if unit.status == "quality_control" and payload.target != "packing":
            await CrmProductionService().transition_unit(
                session,
                production_unit_id=unit.id,
                expected_version=unit.version,
                to_status=CrmProductionUnitStatus.IN_PROGRESS,
                reason_code="ticket_rerouted",
                actor_user_id=actor.id,
                from_terminal=True,
            )
    work.issue = None
    ticket.status = "resolved"
    ticket.resolved_at = datetime.now(timezone.utc)
    ticket.updated_at = ticket.resolved_at
    ticket.version += 1
    ticket.assigned_to_user_id = actor.id
    bag.version += 1
    label = (
        "Продолжить текущий этап" if payload.target == "resume" else STAGE_LABELS[payload.target]
    )
    session.add(
        TicketMessage(
            ticket_id=ticket.id,
            author_user_id=actor.id,
            author_role="system",
            visibility="internal",
            body=f"Решение: {label}. {payload.comment}",
        )
    )
    session.add(
        ProductionEvent(
            bag_id=bag.id,
            unit_id=work.unit_id,
            version=bag.version,
            action="ticket_routed",
            actor_user_id=actor.id,
            command_key=f"ticket:{ticket.id}:v{ticket.version}",
            command_digest=sha256(payload.model_dump_json().encode()).hexdigest(),
            evidence={
                "ticket_id": ticket.id,
                "from_lane": previous_lane,
                "target": payload.target,
                "command": {"note": payload.comment},
            },
            occurred_at=ticket.resolved_at,
        )
    )
    await session.flush()
    return service.summary(ticket)
