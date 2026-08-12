from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class CrmProjectStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CrmProductionUnitStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    QUALITY_CONTROL = "quality_control"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CrmOrderProject(Base, IntegerIdMixin, TimestampMixin):
    """PII-free production projection backed by immutable paid-order evidence."""

    __tablename__ = "crm_order_projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'in_progress', 'on_hold', 'completed', 'cancelled')",
            name="crm_order_project_status_valid",
        ),
        CheckConstraint("version > 0", name="crm_order_project_version_positive"),
        CheckConstraint(
            "order_version_snapshot > 0",
            name="crm_order_project_order_version_positive",
        ),
        CheckConstraint("items_count > 0", name="crm_order_project_items_count_positive"),
        CheckConstraint("units_count > 0", name="crm_order_project_units_count_positive"),
        CheckConstraint(
            "total_price_snapshot >= 0",
            name="crm_order_project_total_nonnegative",
        ),
        CheckConstraint("currency = 'RUB'", name="crm_order_project_currency_rub"),
        CheckConstraint(
            "(status = 'in_progress' AND started_at IS NOT NULL AND closed_at IS NULL) OR "
            "(status = 'completed' AND started_at IS NOT NULL AND closed_at IS NOT NULL) OR "
            "(status = 'cancelled' AND closed_at IS NOT NULL) OR "
            "(status IN ('queued', 'on_hold') AND closed_at IS NULL)",
            name="crm_order_project_lifecycle_timestamps_consistent",
        ),
        Index("ix_crm_order_projects_status_created", "status", "created_at"),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    source_fulfillment_job_id: Mapped[int] = mapped_column(
        ForeignKey("fulfillment_jobs.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    source_payment_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CrmProjectStatus.QUEUED.value,
        server_default=CrmProjectStatus.QUEUED.value,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    order_version_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    items_count: Mapped[int] = mapped_column(Integer, nullable=False)
    units_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_succeeded_at_snapshot: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    units: Mapped[list[CrmProductionUnit]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(CrmProductionUnit.order_item_id, CrmProductionUnit.unit_number)",
    )
    events: Mapped[list[CrmProjectEvent]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CrmProjectEvent.version",
    )


class CrmProductionUnit(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_production_units"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "order_item_id",
            "unit_number",
            name="uq_crm_production_unit_source",
        ),
        CheckConstraint(
            "status IN ('queued', 'in_progress', 'quality_control', 'completed', 'cancelled')",
            name="crm_production_unit_status_valid",
        ),
        CheckConstraint("unit_number > 0", name="crm_production_unit_number_positive"),
        CheckConstraint(
            "product_id_snapshot > 0",
            name="crm_production_unit_product_positive",
        ),
        CheckConstraint(
            "variant_id_snapshot IS NULL OR variant_id_snapshot > 0",
            name="crm_production_unit_variant_positive",
        ),
        CheckConstraint("version > 0", name="crm_production_unit_version_positive"),
        CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND closed_at IS NULL) OR "
            "(status IN ('in_progress', 'quality_control') AND started_at IS NOT NULL "
            "AND closed_at IS NULL) OR "
            "(status = 'completed' AND started_at IS NOT NULL AND closed_at IS NOT NULL) OR "
            "(status = 'cancelled' AND closed_at IS NOT NULL)",
            name="crm_production_unit_lifecycle_timestamps_consistent",
        ),
        Index("ix_crm_production_units_status_created", "status", "created_at"),
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("crm_order_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    variant_id_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    unit_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=CrmProductionUnitStatus.QUEUED.value,
        server_default=CrmProductionUnitStatus.QUEUED.value,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    project: Mapped[CrmOrderProject] = relationship(back_populates="units")


class CrmProjectEvent(Base, IntegerIdMixin):
    __tablename__ = "crm_project_events"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_crm_project_event_version"),
        UniqueConstraint("event_key", name="uq_crm_project_event_key"),
        CheckConstraint("version > 0", name="crm_project_event_version_positive"),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('queued', 'in_progress', 'on_hold', 'completed', 'cancelled')",
            name="crm_project_event_from_status_valid",
        ),
        CheckConstraint(
            "to_status IN ('queued', 'in_progress', 'on_hold', 'completed', 'cancelled')",
            name="crm_project_event_to_status_valid",
        ),
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("crm_order_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    project: Mapped[CrmOrderProject] = relationship(back_populates="events")
