"""Durable order saga; business decisions are separate from provider transport state."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class OrderWorkflow(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "order_workflows"
    __table_args__ = (
        CheckConstraint("version > 0", name="workflow_version_positive"),
        CheckConstraint(
            "(decision IS NULL AND decision_key IS NULL AND decision_actor_id IS NULL AND decision_note IS NULL) OR (decision IS NOT NULL AND decision IN ('approve','reject') AND decision_key IS NOT NULL AND decision_actor_id IS NOT NULL AND decision_note IS NOT NULL)",
            name="workflow_decision_complete",
        ),
        CheckConstraint(
            "state IN ('awaiting_payment','moderation','capture_pending','cancel_pending',"
            "'production','shipped','completed','cancelled','attention')",
            name="workflow_state_valid",
        ),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), unique=True)
    payment_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"), unique=True
    )
    state: Mapped[str] = mapped_column(String(32), default="awaiting_payment", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str | None] = mapped_column(String(16))
    decision_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    decision_actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    decision_note: Mapped[str | None] = mapped_column(Text)
    attention_code: Mapped[str | None] = mapped_column(String(64))
    cdek_status: Mapped[str | None] = mapped_column(String(64))
    cdek_status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderWorkflowEvent(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "order_workflow_events"
    __table_args__ = (UniqueConstraint("workflow_id", "version"),)

    workflow_id: Mapped[int] = mapped_column(ForeignKey("order_workflows.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(64))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class OrderWorkflowJob(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "order_workflow_jobs"
    __table_args__ = (
        UniqueConstraint("workflow_id", "kind", "target_id"),
        CheckConstraint(
            "kind IN ('create_payment','decision','track_delivery')", name="workflow_job_kind"
        ),
        CheckConstraint(
            "status IN ('pending','processing','completed','dead')", name="workflow_job_status"
        ),
        CheckConstraint("failures >= 0 AND generation >= 0", name="workflow_job_counts"),
        CheckConstraint(
            "(kind IN ('create_payment','decision') AND payment_attempt_id = target_id AND payment_attempt_id IS NOT NULL AND shipment_id IS NULL) OR (kind = 'track_delivery' AND shipment_id = target_id AND shipment_id IS NOT NULL AND payment_attempt_id IS NULL)",
            name="workflow_job_target",
        ),
        CheckConstraint(
            "(status = 'processing' AND lease_until IS NOT NULL AND lease_token IS NOT NULL) OR "
            "(status <> 'processing' AND lease_until IS NULL AND lease_token IS NULL)",
            name="workflow_job_lease",
        ),
        Index("ix_workflow_job_due", "status", "available_at"),
    )

    workflow_id: Mapped[int] = mapped_column(ForeignKey("order_workflows.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(32))
    # Immutable attempt ID for payments; immutable shipment ID for read-only delivery polling.
    target_id: Mapped[int] = mapped_column(Integer)
    payment_attempt_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT")
    )
    shipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("cdek_shipments.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(16), default="pending")
    failures: Mapped[int] = mapped_column(Integer, default=0)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
