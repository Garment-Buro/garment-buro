from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin


class CrmProductionPlanStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class CrmProductionUnitEventType(str, Enum):
    INITIALIZED = "initialized"
    PLANNED = "planned"
    STATUS_CHANGED = "status_changed"


class CrmProductionPlanRevision(Base, IntegerIdMixin):
    __tablename__ = "crm_production_plan_revisions"
    __table_args__ = (
        UniqueConstraint(
            "production_unit_id",
            "revision_number",
            name="uq_crm_production_plan_revision_number",
        ),
        UniqueConstraint(
            "production_unit_id",
            "id",
            name="uq_crm_production_plan_unit_identity",
        ),
        ForeignKeyConstraint(
            ["production_unit_id", "based_on_plan_revision_id"],
            [
                "crm_production_plan_revisions.production_unit_id",
                "crm_production_plan_revisions.id",
            ],
            name="fk_crm_production_plan_same_unit_base",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('active', 'superseded')",
            name="crm_production_plan_status_valid",
        ),
        CheckConstraint(
            "revision_number > 0",
            name="crm_production_plan_revision_positive",
        ),
        CheckConstraint(
            "length(evidence_sha256) = 64",
            name="crm_production_plan_evidence_digest_length",
        ),
        Index(
            "uq_crm_production_plan_active",
            "production_unit_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    production_unit_id: Mapped[int] = mapped_column(
        ForeignKey("crm_production_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    based_on_plan_revision_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    garment_model_id: Mapped[int] = mapped_column(
        ForeignKey("crm_garment_models.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    garment_size_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_garment_sizes.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    tech_card_revision_id: Mapped[int] = mapped_column(
        ForeignKey("crm_tech_card_revisions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CrmProductionPlanStatus.ACTIVE.value,
        server_default=CrmProductionPlanStatus.ACTIVE.value,
        index=True,
    )
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    planned_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    planned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class CrmProductionUnitEvent(Base, IntegerIdMixin):
    __tablename__ = "crm_production_unit_events"
    __table_args__ = (
        UniqueConstraint(
            "production_unit_id",
            "version",
            name="uq_crm_production_unit_event_version",
        ),
        UniqueConstraint("event_key", name="uq_crm_production_unit_event_key"),
        CheckConstraint("version > 0", name="crm_production_unit_event_version_positive"),
        CheckConstraint(
            "event_type IN ('initialized', 'planned', 'status_changed')",
            name="crm_production_unit_event_type_valid",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('queued', 'in_progress', 'quality_control', 'completed', 'cancelled')",
            name="crm_production_unit_event_from_status_valid",
        ),
        CheckConstraint(
            "to_status IN ('queued', 'in_progress', 'quality_control', 'completed', 'cancelled')",
            name="crm_production_unit_event_to_status_valid",
        ),
        CheckConstraint(
            "(event_type = 'initialized' AND from_status IS NULL "
            "AND production_plan_revision_id IS NULL) OR "
            "(event_type = 'planned' AND from_status = to_status "
            "AND production_plan_revision_id IS NOT NULL) OR "
            "(event_type = 'status_changed' AND from_status IS NOT NULL "
            "AND from_status <> to_status)",
            name="crm_production_unit_event_shape_valid",
        ),
    )

    production_unit_id: Mapped[int] = mapped_column(
        ForeignKey("crm_production_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    production_plan_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_production_plan_revisions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
