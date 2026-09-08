"""PII-free diagnostics and authorized recovery; never manufacture provider success."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.delivery.models import CdekShipment
from app.modules.fulfillment.models import FulfillmentJob
from app.modules.identity.security import ensure_utc
from app.modules.orders.models import Order
from app.modules.orders.workflow import OrderWorkflowConflict, authorize_moderator
from app.modules.orders.workflow_models import OrderWorkflow, OrderWorkflowEvent, OrderWorkflowJob
from app.modules.orders.workflow_repository import workflow_for_order
from app.modules.payments.models import PaymentAttempt, PaymentOperation, PaymentReconciliationJob


async def inspect_orders(
    session: AsyncSession,
    *,
    order_id: int | None = None,
    before_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    if not 1 <= limit <= 500:
        raise ValueError("limit must be 1..500")
    query = select(OrderWorkflow).order_by(OrderWorkflow.id.desc()).limit(limit)
    if order_id is not None:
        query = query.where(OrderWorkflow.order_id == order_id)
    if before_id is not None:
        query = query.where(OrderWorkflow.id < before_id)
    result = []
    now = datetime.now(timezone.utc)
    for flow in await session.scalars(query):
        jobs = list(
            await session.scalars(
                select(OrderWorkflowJob).where(OrderWorkflowJob.workflow_id == flow.id)
            )
        )
        fulfillment = list(
            await session.scalars(
                select(FulfillmentJob).where(FulfillmentJob.order_id == flow.order_id)
            )
        )
        reconciliation = await session.scalar(
            select(PaymentReconciliationJob).where(
                PaymentReconciliationJob.payment_attempt_id == flow.payment_attempt_id
            )
        )
        payment = await session.get(PaymentAttempt, flow.payment_attempt_id)
        shipment = await session.scalar(
            select(CdekShipment).where(CdekShipment.order_id == flow.order_id)
        )
        result.append(
            {
                "cursor": flow.id,
                "order_id": flow.order_id,
                "state": flow.state,
                "version": flow.version,
                "hold_expires_at": str(flow.hold_expires_at) if flow.hold_expires_at else None,
                "hold_needs_attention": bool(
                    flow.state in {"moderation", "capture_pending"}
                    and flow.hold_expires_at
                    and ensure_utc(flow.hold_expires_at) <= now + timedelta(hours=4)
                ),
                "attention": flow.attention_code,
                "payment": {"status": payment.status, "error": payment.last_error_code},
                "workflow_jobs": [
                    {
                        "id": j.id,
                        "kind": j.kind,
                        "status": j.status,
                        "generation": j.generation,
                        "failures": j.failures,
                        "error": j.last_error_code,
                        "available_at": str(j.available_at),
                        "lease_until": str(j.lease_until) if j.lease_until else None,
                    }
                    for j in jobs
                ],
                "fulfillment_jobs": [
                    {
                        "id": j.id,
                        "kind": j.kind,
                        "status": j.status,
                        "generation": j.attempts_count,
                        "error": j.last_error_code,
                    }
                    for j in fulfillment
                ],
                "reconciliation": {
                    "id": reconciliation.id,
                    "status": reconciliation.status,
                    "generation": reconciliation.attempts_count,
                    "error": reconciliation.last_error_code,
                    "last_checked_at": str(reconciliation.last_checked_at),
                }
                if reconciliation
                else None,
                "shipment": {
                    "id": shipment.id,
                    "status": shipment.status,
                    "tracking": shipment.provider_cdek_number,
                    "error": shipment.last_error_code,
                    "cdek_status": flow.cdek_status,
                }
                if shipment
                else None,
            }
        )
    return result


async def requeue(
    session: AsyncSession, *, family: str, job_id: int, expected_generation: int, actor_id: int
) -> None:
    await authorize_moderator(session, actor_id)
    models = {
        "workflow": OrderWorkflowJob,
        "fulfillment": FulfillmentJob,
        "reconciliation": PaymentReconciliationJob,
    }
    model = models.get(family)
    if model is None:
        raise ValueError("Unsupported recovery queue")
    row = await session.get(model, job_id)
    if row is None:
        raise OrderWorkflowConflict("Job not found")
    if family == "workflow":
        flow = await session.get(OrderWorkflow, row.workflow_id)
    elif family == "fulfillment":
        flow = await session.scalar(
            select(OrderWorkflow).where(OrderWorkflow.order_id == row.order_id)
        )
    else:
        flow = await session.scalar(
            select(OrderWorkflow).where(OrderWorkflow.payment_attempt_id == row.payment_attempt_id)
        )
    if flow is None:
        raise OrderWorkflowConflict("Recovery is limited to managed orders")
    await session.scalar(select(Order).where(Order.id == flow.order_id).with_for_update())
    flow = await workflow_for_order(session, flow.order_id)
    row = await session.scalar(
        select(model)
        .where(model.id == job_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    generation = row.generation if family == "workflow" else row.attempts_count
    if row.status != "dead" or generation != expected_generation:
        raise OrderWorkflowConflict(
            "Reload job: only the inspected dead generation may be requeued"
        )
    if family == "workflow":
        # Human-authorized retry keeps the original immutable provider key/body/window.
        if row.kind == "decision":
            operation = await session.scalar(
                select(PaymentOperation)
                .where(PaymentOperation.payment_attempt_id == flow.payment_attempt_id)
                .with_for_update()
            )
            if operation is not None and operation.status == "failed":
                operation.status, operation.resolved_at = "unknown", None
        elif row.kind == "create_payment":
            attempt = await session.get(PaymentAttempt, flow.payment_attempt_id)
            if attempt.status == "failed":
                attempt.status, attempt.resolved_at = "unknown", None
        row.failures = 0
        row.status = "pending"
    elif family == "fulfillment":
        # Preserve append-only fulfillment attempt numbers.
        if row.attempts_count >= 20:
            raise OrderWorkflowConflict(
                "20 attempts exhausted: investigate the handler before changing its retry budget"
            )
        row.max_attempts = max(row.max_attempts, row.attempts_count + 1)
        row.status = "retry"
    else:
        row.attempts_count = 0
        row.status = "scheduled"
    row.available_at = datetime.now(timezone.utc)
    flow.version += 1
    session.add(
        OrderWorkflowEvent(
            workflow_id=flow.id,
            version=flow.version,
            state=flow.state,
            reason=f"ops.requeue_{family}_{job_id}_{generation}",
            actor_user_id=actor_id,
        )
    )
    await session.flush()
