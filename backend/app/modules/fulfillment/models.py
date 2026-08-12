from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class FulfillmentJobKind(str, Enum):
    CUSTOMER_PAYMENT_EMAIL = "customer_payment_email"
    CDEK_ORDER_CREATE = "cdek_order_create"
    CRM_ORDER_PROJECT = "crm_order_project"


class FulfillmentJobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRY = "retry"
    COMPLETED = "completed"
    DEAD = "dead"


class FulfillmentJobAttemptStatus(str, Enum):
    PROCESSING = "processing"
    RETRY = "retry"
    COMPLETED = "completed"
    DEAD = "dead"
    ABANDONED = "abandoned"


class FulfillmentJob(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "fulfillment_jobs"
    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "kind",
            name="uq_fulfillment_job_order_kind",
        ),
        CheckConstraint(
            "kind IN ('customer_payment_email', 'cdek_order_create', 'crm_order_project')",
            name="fulfillment_job_kind_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'retry', 'completed', 'dead')",
            name="fulfillment_job_status_valid",
        ),
        CheckConstraint(
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name="fulfillment_job_attempts_valid",
        ),
        CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 20",
            name="fulfillment_job_max_attempts_valid",
        ),
        CheckConstraint(
            "(status = 'processing' AND locked_at IS NOT NULL AND locked_by IS NOT NULL) OR "
            "(status <> 'processing' AND locked_at IS NULL AND locked_by IS NULL)",
            name="fulfillment_job_lock_consistent",
        ),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name="fulfillment_job_completed_at_consistent",
        ),
        Index("ix_fulfillment_jobs_dispatch", "status", "available_at"),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_payment_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=FulfillmentJobStatus.PENDING.value,
        server_default=FulfillmentJobStatus.PENDING.value,
        index=True,
    )
    attempts_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    result_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    attempts: Mapped[list[FulfillmentJobAttempt]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FulfillmentJobAttempt.attempt_number",
    )


class FulfillmentJobAttempt(Base, IntegerIdMixin):
    __tablename__ = "fulfillment_job_attempts"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "attempt_number",
            name="uq_fulfillment_job_attempt_number",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="fulfillment_job_attempt_number_positive",
        ),
        CheckConstraint(
            "status IN ('processing', 'retry', 'completed', 'dead', 'abandoned')",
            name="fulfillment_job_attempt_status_valid",
        ),
        CheckConstraint(
            "(status = 'processing' AND finished_at IS NULL) OR "
            "(status <> 'processing' AND finished_at IS NOT NULL)",
            name="fulfillment_job_attempt_finished_consistent",
        ),
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("fulfillment_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)

    job: Mapped[FulfillmentJob] = relationship(back_populates="attempts")
