"""At-least-once processing with durable intents, fenced leases and bounded recovery."""

import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.delivery.models import CdekShipment
from app.modules.delivery.provider import CdekProvider, CdekProviderError
from app.modules.delivery.tracking import apply_tracking
from app.modules.orders.service import OrderLifecycleService
from app.modules.orders.workflow_models import OrderWorkflow, OrderWorkflowJob
from app.modules.orders.workflow_repository import claim, enqueue, workflow_for_order
from app.modules.payments.creation import (
    PaymentCreationFailedError,
    PaymentCreationInProgressError,
    PaymentCreationRetryExpiredError,
    PaymentCreationService,
)
from app.modules.payments.models import PaymentAttempt, PaymentOperation
from app.modules.payments.operation_service import (
    PaymentOperationConflictError,
    PaymentOperationFailedError,
    PaymentOperationInProgressError,
    PaymentOperationService,
)
from app.modules.payments.provider import YooKassaProvider, YooKassaProviderError
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.service import PaymentService

logger = logging.getLogger(__name__)


class WorkflowLeaseLost(RuntimeError):
    pass


class OrderWorkflowProcessor:
    def __init__(
        self, settings: Settings, payments: YooKassaProvider, delivery: CdekProvider | None = None
    ):
        self.settings, self.payments, self.delivery = settings, payments, delivery

    async def seed_tracking(self, session: AsyncSession, now: datetime, limit: int = 100) -> int:
        if not self.settings.cdek_tracking_enabled:
            return 0
        rows = (
            await session.execute(
                select(OrderWorkflow, CdekShipment.id)
                .join(CdekShipment, CdekShipment.order_id == OrderWorkflow.order_id)
                .where(
                    OrderWorkflow.state.in_(("production", "shipped")),
                    CdekShipment.provider_uuid.is_not(None),
                    CdekShipment.status.in_(("created", "unknown")),
                    ~select(OrderWorkflowJob.id)
                    .where(
                        OrderWorkflowJob.workflow_id == OrderWorkflow.id,
                        OrderWorkflowJob.kind == "track_delivery",
                    )
                    .exists(),
                )
                .order_by(OrderWorkflow.id)
                .limit(limit)
                .with_for_update(of=OrderWorkflow, skip_locked=True)
            )
        ).all()
        for flow, shipment_id in rows:
            await enqueue(session, flow, "track_delivery", shipment_id, now)
        await session.commit()
        return len(rows)

    async def process_once(
        self, session: AsyncSession, *, now: datetime | None = None
    ) -> int | None:
        now = now or datetime.now(timezone.utc)
        job = await claim(session, now)
        if job is None:
            return None
        job_id, token, kind, target_id, flow_id = (
            job.id,
            job.lease_token,
            job.kind,
            job.target_id,
            job.workflow_id,
        )
        await session.commit()
        completed, error, permanent, delay = False, None, False, 30
        try:
            if kind == "create_payment":
                flow = await session.get(OrderWorkflow, flow_id)
                if flow is None or flow.payment_attempt_id != target_id:
                    raise ValueError("Payment job target does not match workflow")
                await PaymentCreationService(self.settings, self.payments).create_attempt(
                    session, attempt_id=target_id, now=now
                )
                completed = True
            elif kind == "decision":
                await self._decision(session, flow_id=flow_id, attempt_id=target_id, now=now)
                completed = True
            elif kind == "track_delivery":
                if not self.settings.cdek_tracking_enabled or self.delivery is None:
                    delay = 300
                else:
                    shipment = await session.get(CdekShipment, target_id)
                    if shipment is None or shipment.provider_uuid is None:
                        raise ValueError("CDEK identity missing")
                    flow = await session.get(OrderWorkflow, flow_id)
                    if flow is None or flow.order_id != shipment.order_id:
                        raise ValueError("Delivery job target does not match workflow")
                    snapshot = await self.delivery.get_order(shipment.provider_uuid)
                    # apply_tracking locks order first; final fenced acknowledgement commits
                    # its changes together or rolls them all back if this lease was lost.
                    completed = await apply_tracking(
                        session, self.settings, shipment_id=target_id, snapshot=snapshot, now=now
                    )
                    delay = 300
            else:
                raise ValueError("Unknown job kind")
        except (PaymentCreationInProgressError, PaymentOperationInProgressError):
            await session.rollback()
            delay = 60
        except PaymentCreationRetryExpiredError:
            await session.rollback()
            error, permanent = "idempotence_window_expired", True
        except (PaymentCreationFailedError, PaymentOperationFailedError) as exc:
            await session.rollback()
            error = exc.code
            permanent = not exc.outcome_unknown or exc.code == "idempotence_window_expired"
        except (CdekProviderError, YooKassaProviderError) as exc:
            await session.rollback()
            error, permanent = exc.code, not exc.retryable
        except (ValueError, PaymentOperationConflictError):
            await session.rollback()
            error, permanent = "workflow_evidence_conflict", True
        except WorkflowLeaseLost:
            await session.rollback()
            return job_id
        except Exception:  # noqa: BLE001 - the durable intent survives unexpected defects
            await session.rollback()
            error = "processing_unexpected"
        try:
            stored = await self._owned(session, job_id, token)
        except WorkflowLeaseLost:
            await session.rollback()
            return job_id
        if error:
            stored.failures += 1
            delay = min(1800, 30 * 2 ** min(stored.failures - 1, 6)) + random.randint(0, 15)
        else:
            stored.failures = 0
        stored.status = (
            "completed"
            if completed
            else "dead"
            if permanent or stored.failures >= 12
            else "pending"
        )
        stored.last_error_code = error
        stored.available_at = now + timedelta(seconds=delay)
        stored.lease_token = stored.lease_until = None
        await session.commit()
        if stored.status == "dead":
            logger.error("Order workflow job %s requires intervention: %s", job_id, error)
        return job_id

    async def _decision(
        self, session: AsyncSession, *, flow_id: int, attempt_id: int, now: datetime
    ) -> None:
        flow = await session.get(OrderWorkflow, flow_id)
        attempt = await session.get(PaymentAttempt, attempt_id)
        if (
            flow is None
            or attempt is None
            or attempt.id != flow.payment_attempt_id
            or attempt.provider_payment_id is None
        ):
            raise ValueError("Missing moderation payment evidence")
        # Always GET before retrying a POST, including after process termination.
        snapshot = await self.payments.get_payment(attempt.provider_payment_id)
        attempt = await PaymentRepository().get_attempt_for_update(session, attempt_id=attempt_id)
        await PaymentService(self.settings).record_provider_snapshot(
            session, attempt_id=attempt_id, snapshot=snapshot, now=now
        )
        if snapshot.status == "succeeded":
            await OrderLifecycleService(self.settings).confirm_payment(
                session, order_id=flow.order_id, payment_attempt_id=attempt_id, now=now
            )
        flow = await workflow_for_order(session, flow.order_id)
        if snapshot.status in {"succeeded", "canceled"}:
            operation = await session.scalar(
                select(PaymentOperation)
                .where(PaymentOperation.payment_attempt_id == attempt_id)
                .with_for_update()
            )
            if operation is not None:
                expected = "succeeded" if operation.operation_type == "capture" else "canceled"
                operation.status = "succeeded" if snapshot.status == expected else "failed"
                operation.resolved_at = now
                operation.last_error_code = (
                    None if snapshot.status == expected else "provider_terminal_state"
                )
            await session.commit()
            return
        decision, actor_id = flow.decision, flow.decision_actor_id
        key = f"moderation_{flow.id}_{flow.decision_key}"
        await session.commit()
        operations = PaymentOperationService(self.settings, self.payments)
        if decision == "approve":
            await operations.capture(
                session, attempt_id=attempt_id, client_key=key, actor_user_id=actor_id, now=now
            )
        elif decision == "reject":
            await operations.cancel(
                session, attempt_id=attempt_id, client_key=key, actor_user_id=actor_id, now=now
            )
        else:
            raise ValueError("Missing moderation decision")

    @staticmethod
    async def _owned(session: AsyncSession, job_id: int, token: str) -> OrderWorkflowJob:
        job = await session.scalar(
            select(OrderWorkflowJob)
            .where(OrderWorkflowJob.id == job_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if job is None or job.status != "processing" or job.lease_token != token:
            raise WorkflowLeaseLost("A newer generation owns this job")
        return job
