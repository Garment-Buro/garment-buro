from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.workflow_models import OrderWorkflow, OrderWorkflowEvent, OrderWorkflowJob


async def workflow_for_order(session: AsyncSession, order_id: int) -> OrderWorkflow | None:
    return await session.scalar(
        select(OrderWorkflow)
        .where(OrderWorkflow.order_id == order_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def transition(session: AsyncSession, flow: OrderWorkflow, state: str, reason: str) -> None:
    if flow.state == state:
        return
    flow.state = state
    flow.version += 1
    session.add(
        OrderWorkflowEvent(
            workflow_id=flow.id,
            version=flow.version,
            state=state,
            reason=reason,
            actor_user_id=flow.decision_actor_id,
        )
    )


async def enqueue(
    session: AsyncSession, flow: OrderWorkflow, kind: str, target_id: int, now: datetime
) -> OrderWorkflowJob:
    # Caller holds the workflow row lock; unique constraint is the final backstop.
    job = await session.scalar(
        select(OrderWorkflowJob).where(
            OrderWorkflowJob.workflow_id == flow.id,
            OrderWorkflowJob.kind == kind,
            OrderWorkflowJob.target_id == target_id,
        )
    )
    if job is None:
        job = OrderWorkflowJob(
            workflow_id=flow.id, kind=kind, target_id=target_id, available_at=now
        )
        if kind == "track_delivery":
            job.shipment_id = target_id
        else:
            job.payment_attempt_id = target_id
        session.add(job)
        await session.flush()
    return job


async def claim(session: AsyncSession, now: datetime) -> OrderWorkflowJob | None:
    job = await session.scalar(
        select(OrderWorkflowJob)
        .where(
            or_(
                (OrderWorkflowJob.status == "pending") & (OrderWorkflowJob.available_at <= now),
                (OrderWorkflowJob.status == "processing") & (OrderWorkflowJob.lease_until <= now),
            )
        )
        .order_by(OrderWorkflowJob.available_at, OrderWorkflowJob.id)
        .limit(1)
        .execution_options(populate_existing=True)
        .with_for_update(skip_locked=True)
    )
    if job is not None:
        job.status = "processing"
        job.generation += 1
        job.lease_token = str(uuid4())
        job.lease_until = now + timedelta(minutes=5)
    return job
