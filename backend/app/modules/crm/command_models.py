from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin


class CrmStaffCommandType(str, Enum):
    PROJECT_ASSIGN = "project.assign"
    PROJECT_TRANSITION = "project.transition"
    UNIT_ASSIGN = "unit.assign"
    UNIT_PLAN = "unit.plan"
    UNIT_TRANSITION = "unit.transition"


class CrmStaffCommandStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"


class CrmAssignmentEvent(Base, IntegerIdMixin):
    __tablename__ = "crm_assignment_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_crm_assignment_event_key"),
        UniqueConstraint(
            "production_project_id",
            "entity_version",
            name="uq_crm_assignment_project_version",
        ),
        UniqueConstraint(
            "production_unit_id",
            "entity_version",
            name="uq_crm_assignment_unit_version",
        ),
        CheckConstraint(
            "(production_project_id IS NOT NULL AND production_unit_id IS NULL) OR "
            "(production_project_id IS NULL AND production_unit_id IS NOT NULL)",
            name="crm_assignment_exactly_one_target",
        ),
        CheckConstraint("entity_version > 0", name="crm_assignment_version_positive"),
        CheckConstraint(
            "(from_assigned_to_user_id IS NULL AND to_assigned_to_user_id IS NOT NULL) OR "
            "(from_assigned_to_user_id IS NOT NULL AND to_assigned_to_user_id IS NULL) OR "
            "(from_assigned_to_user_id IS NOT NULL AND to_assigned_to_user_id IS NOT NULL "
            "AND from_assigned_to_user_id <> to_assigned_to_user_id)",
            name="crm_assignment_changed",
        ),
    )

    production_project_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_order_projects.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    production_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_production_units.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    from_assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    to_assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
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
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )


class CrmStaffCommand(Base, IntegerIdMixin):
    __tablename__ = "crm_staff_commands"
    __table_args__ = (
        CheckConstraint(
            "command_type IN ('project.assign', 'project.transition', "
            "'unit.assign', 'unit.plan', 'unit.transition')",
            name="crm_staff_command_type_valid",
        ),
        CheckConstraint(
            "status IN ('processing', 'completed')",
            name="crm_staff_command_status_valid",
        ),
        CheckConstraint("target_id > 0", name="crm_staff_command_target_positive"),
        CheckConstraint(
            "length(idempotency_key_sha256) = 64 AND length(command_sha256) = 64",
            name="crm_staff_command_digests_valid",
        ),
        CheckConstraint(
            "(status = 'processing' AND result_version IS NULL AND completed_at IS NULL) OR "
            "(status = 'completed' AND result_version > 0 AND completed_at IS NOT NULL)",
            name="crm_staff_command_completion_consistent",
        ),
    )

    idempotency_key_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    command_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    command_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CrmStaffCommandStatus.PROCESSING.value,
        server_default=CrmStaffCommandStatus.PROCESSING.value,
        index=True,
    )
    result_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
