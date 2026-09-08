"""Order saga commands. No HTTP endpoint: moderation is an audited backend operation."""

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.identity.models import Permission, RolePermission, User, UserRole
from app.modules.identity.security import ensure_utc
from app.modules.inventory.repository import InventoryRepository
from app.modules.orders.models import Order
from app.modules.orders.workflow_models import OrderWorkflow, OrderWorkflowEvent
from app.modules.orders.workflow_repository import enqueue, transition, workflow_for_order
from app.modules.payments.models import PaymentAttempt
from app.modules.payments.repository import PaymentRepository


class OrderWorkflowConflict(ValueError):
    pass


class OrderModerationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def attach(
        self, session: AsyncSession, *, order_id: int, attempt_id: int, now: datetime
    ) -> OrderWorkflow:
        # Checkout already owns the order row and commits this with order + payment intent.
        flow = await workflow_for_order(session, order_id)
        if flow is None:
            flow = OrderWorkflow(
                order_id=order_id,
                payment_attempt_id=attempt_id,
                state="awaiting_payment",
                version=1,
            )
            session.add(flow)
            await session.flush()
            session.add(
                OrderWorkflowEvent(
                    workflow_id=flow.id, version=1, state=flow.state, reason="checkout.prepared"
                )
            )
        if flow.payment_attempt_id != attempt_id:
            raise OrderWorkflowConflict("Managed order cannot replace its payment identity")
        await enqueue(session, flow, "create_payment", attempt_id, now)
        return flow

    async def decide(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        expected_version: int,
        actor_user_id: int,
        decision: str,
        key: str,
        note: str,
        now: datetime | None = None,
    ) -> OrderWorkflow:
        if (
            decision not in {"approve", "reject"}
            or not 8 <= len(key) <= 128
            or not 1 <= len(note.strip()) <= 2000
        ):
            raise OrderWorkflowConflict("Decision, idempotency key and reason are required")
        now = ensure_utc(now or datetime.now(timezone.utc))
        await authorize_moderator(session, actor_user_id)
        await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
        flow = await workflow_for_order(session, order_id)
        if flow is None:
            raise OrderWorkflowConflict("Order is not managed by moderation")
        digest = hashlib.sha256(key.encode()).hexdigest()
        if flow.decision_key is not None:
            if (flow.decision_key, flow.decision, flow.decision_actor_id, flow.decision_note) != (
                digest,
                decision,
                actor_user_id,
                note.strip(),
            ):
                raise OrderWorkflowConflict("Order already has a different moderation decision")
            return flow
        if flow.version != expected_version or flow.state != "moderation":
            raise OrderWorkflowConflict("Reload order: state or version changed")
        attempt = await PaymentRepository().get_attempt_for_update(
            session, attempt_id=flow.payment_attempt_id
        )
        if attempt is None or attempt.status != "waiting_for_capture":
            raise OrderWorkflowConflict("Verified payment hold is required")
        if decision == "approve" and (
            flow.hold_expires_at is None
            or ensure_utc(flow.hold_expires_at) <= now + timedelta(minutes=2)
        ):
            raise OrderWorkflowConflict("Hold expires too soon; reconcile payment, do not capture")
        flow.decision, flow.decision_key = decision, digest
        flow.decision_actor_id, flow.decision_note = actor_user_id, note.strip()
        transition(
            session,
            flow,
            "capture_pending" if decision == "approve" else "cancel_pending",
            "moderation." + decision,
        )
        await enqueue(session, flow, "decision", attempt.id, now)
        await session.flush()
        return flow


async def authorize_moderator(session: AsyncSession, actor_id: int) -> None:
    allowed = await session.scalar(
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(RolePermission, RolePermission.role_id == UserRole.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(User.id == actor_id, User.status == "active", Permission.code == "payments.manage")
        .limit(1)
    )
    if allowed is None:
        raise PermissionError("Active staff with payments.manage permission is required")


async def apply_payment_observation(
    session: AsyncSession, settings: Settings, attempt: PaymentAttempt, now: datetime
) -> None:
    """Called only after authenticated provider evidence validation, within its transaction."""
    flow = await workflow_for_order(session, attempt.payment.order_id)
    if flow is None:
        return
    if flow.payment_attempt_id != attempt.id:
        raise OrderWorkflowConflict("Payment does not match the order workflow")
    if attempt.status == "waiting_for_capture" and flow.state == "awaiting_payment":
        flow.hold_expires_at = attempt.expires_at
        if attempt.expires_at is None:
            flow.attention_code = "hold_deadline_missing"
            transition(session, flow, "attention", flow.attention_code)
        else:
            transition(session, flow, "moderation", "payment.authorized")
    elif attempt.status == "succeeded" and flow.state not in {"production", "shipped", "completed"}:
        if flow.decision != "approve":
            flow.attention_code = "captured_without_approval"
            transition(session, flow, "attention", flow.attention_code)
        else:
            # Reservation expiry is handled by the provider-aware saga, never the old timer.
            reservations = await InventoryRepository().list_order_reservations_for_update(
                session, order_id=flow.order_id
            )
            for reservation in reservations:
                if reservation.status == "active":
                    reservation.expires_at = max(
                        ensure_utc(reservation.expires_at), now + timedelta(minutes=5)
                    )
            # Release to production happens only in confirm_payment with inventory + outbox.
            transition(session, flow, "capture_pending", "payment.captured")
    elif attempt.status == "canceled" and flow.state not in {
        "production",
        "shipped",
        "completed",
        "cancelled",
    }:
        from app.modules.orders.service import OrderLifecycleService

        await OrderLifecycleService(settings).cancel_pending(
            session, order_id=flow.order_id, reason_code="payment.hold_cancelled", now=now
        )
        transition(session, flow, "cancelled", "payment.hold_cancelled")
    await session.flush()


def customer_stage(flow: OrderWorkflow | None) -> tuple[str | None, str | None]:
    if flow is None:
        return None, None
    states = {
        "moderation": ("moderation", "Модерация"),
        "capture_pending": ("moderation", "Модерация"),
        "cancel_pending": ("moderation", "Модерация"),
        "production": ("production", "Производство"),
        "shipped": ("shipped", "Передано в СДЭК"),
        "completed": ("completed", "Выполнено"),
    }
    return states.get(flow.state, (None, None))
