from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class AdminInboxKind(str, Enum):
    SUPPORT = "support"
    PRODUCTION_PROBLEM = "production_problem"


class AdminInboxStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AdminInboxPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AdminInboxItem(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "admin_inbox_items"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('support','production_problem')",
            name="admin_inbox_kind_valid",
        ),
        CheckConstraint(
            "status IN ('new','in_progress','resolved','closed')",
            name="admin_inbox_status_valid",
        ),
        CheckConstraint(
            "priority IN ('low','normal','high','critical')",
            name="admin_inbox_priority_valid",
        ),
        CheckConstraint("version > 0", name="admin_inbox_version_positive"),
        CheckConstraint(
            "(status IN ('resolved','closed') AND resolved_at IS NOT NULL) OR "
            "(status IN ('new','in_progress') AND resolved_at IS NULL)",
            name="admin_inbox_resolution_consistent",
        ),
        Index("ix_admin_inbox_kind_status_created", "kind", "status", "created_at"),
    )

    kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=AdminInboxStatus.NEW.value,
        server_default=AdminInboxStatus.NEW.value,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AdminInboxPriority.NORMAL.value,
        server_default=AdminInboxPriority.NORMAL.value,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reporter_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reporter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reporter_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reporter_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_order_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    production_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_production_units.id", ondelete="SET NULL"), nullable=True, index=True
    )
    station: Mapped[str | None] = mapped_column(String(24), nullable=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
