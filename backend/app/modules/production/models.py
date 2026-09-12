from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin

JSON_DATA = JSON().with_variant(JSONB, "postgresql")


class ProductionDemoEmployee(Base, IntegerIdMixin):
    """Explicitly restricted demo accounts, never identified by editable profile fields."""

    __tablename__ = "production_demo_employees"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    station: Mapped[str] = mapped_column(String(24), unique=True)


class ProductionBag(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "production_bags"
    __table_args__ = (
        CheckConstraint("version > 0", name="production_bag_version_positive"),
        CheckConstraint("flow_version IN (1,2)", name="production_flow_version_valid"),
        CheckConstraint(
            "state IN ('inbox','kitting','workshop','waiting_dtf','packed','dispatched')",
            name="production_bag_state_valid",
        ),
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("crm_order_projects.id", ondelete="RESTRICT"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(24), default="inbox", index=True)
    tracking_number: Mapped[str | None] = mapped_column(String(100))
    flow_version: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    public_token: Mapped[str | None] = mapped_column(String(64), unique=True)


class ProductionSpecification(Base, IntegerIdMixin):
    __tablename__ = "production_specifications"
    __table_args__ = (UniqueConstraint("unit_id", "revision"),)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("crm_production_units.id", ondelete="RESTRICT"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("crm_production_plan_revisions.id", ondelete="RESTRICT")
    )
    order_evidence: Mapped[dict] = mapped_column(JSON_DATA)
    order_digest: Mapped[str] = mapped_column(String(64))
    specification: Mapped[dict] = mapped_column(JSON_DATA)
    specification_digest: Mapped[str] = mapped_column(String(64))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductionWorkItem(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "production_work_items"
    __table_args__ = (
        CheckConstraint("stage_index >= 0", name="work_item_stage_nonnegative"),
        CheckConstraint(
            "lane IS NULL OR lane IN ('cut','kit','waiting_dtf','workshop','packing','done')",
            name="production_lane_valid",
        ),
    )
    bag_id: Mapped[int] = mapped_column(
        ForeignKey("production_bags.id", ondelete="RESTRICT"), index=True
    )
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("crm_production_units.id", ondelete="RESTRICT"), unique=True
    )
    specification_id: Mapped[int | None] = mapped_column(
        ForeignKey("production_specifications.id", ondelete="RESTRICT")
    )
    documents_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    component_checks: Mapped[dict] = mapped_column(JSON_DATA, default=dict)
    dtf_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    dtf_inserted: Mapped[bool] = mapped_column(Boolean, default=False)
    stage_index: Mapped[int] = mapped_column(Integer, default=0)
    issue: Mapped[str | None] = mapped_column(Text)
    lane: Mapped[str | None] = mapped_column(String(24), index=True)
    public_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    dtf_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductionEvent(Base, IntegerIdMixin):
    __tablename__ = "production_events"
    __table_args__ = (UniqueConstraint("bag_id", "version"), UniqueConstraint("command_key"))
    bag_id: Mapped[int] = mapped_column(
        ForeignKey("production_bags.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_production_units.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    command_key: Mapped[str] = mapped_column(String(128))
    command_digest: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[dict] = mapped_column(JSON_DATA)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ProductionSpecificationFile(Base, IntegerIdMixin):
    __tablename__ = "production_specification_files"
    __table_args__ = (UniqueConstraint("specification_id", "attachment_id"),)
    specification_id: Mapped[int] = mapped_column(
        ForeignKey("production_specifications.id", ondelete="RESTRICT"), index=True
    )
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("crm_file_attachments.id", ondelete="RESTRICT")
    )
    role: Mapped[str] = mapped_column(String(16))
