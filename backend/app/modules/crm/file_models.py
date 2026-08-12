from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin
from app.modules.media.models import MediaObject


class CrmFileRole(str, Enum):
    PATTERN = "pattern"
    TECH_CARD_SOURCE = "tech_card_source"
    PRODUCTION_EVIDENCE = "production_evidence"


class CrmFileAttachment(Base, IntegerIdMixin):
    __tablename__ = "crm_file_attachments"
    __table_args__ = (
        UniqueConstraint(
            "tech_card_revision_id",
            "role",
            "sort_order",
            name="uq_crm_file_tech_card_role_order",
        ),
        UniqueConstraint(
            "production_project_id",
            "role",
            "sort_order",
            name="uq_crm_file_project_role_order",
        ),
        UniqueConstraint(
            "production_unit_id",
            "role",
            "sort_order",
            name="uq_crm_file_unit_role_order",
        ),
        CheckConstraint(
            "role IN ('pattern', 'tech_card_source', 'production_evidence')",
            name="crm_file_role_valid",
        ),
        CheckConstraint("sort_order >= 0", name="crm_file_sort_order_nonnegative"),
        CheckConstraint(
            "(tech_card_revision_id IS NOT NULL AND production_project_id IS NULL "
            "AND production_unit_id IS NULL) OR "
            "(tech_card_revision_id IS NULL AND production_project_id IS NOT NULL "
            "AND production_unit_id IS NULL) OR "
            "(tech_card_revision_id IS NULL AND production_project_id IS NULL "
            "AND production_unit_id IS NOT NULL)",
            name="crm_file_exactly_one_target",
        ),
        CheckConstraint(
            "(tech_card_revision_id IS NOT NULL AND role IN ('pattern', 'tech_card_source')) OR "
            "((production_project_id IS NOT NULL OR production_unit_id IS NOT NULL) "
            "AND role = 'production_evidence')",
            name="crm_file_role_target_valid",
        ),
    )

    media_object_id: Mapped[int] = mapped_column(
        ForeignKey("media_objects.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    tech_card_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_tech_card_revisions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
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
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    media: Mapped[MediaObject] = relationship()


class CrmFileAccessEvent(Base, IntegerIdMixin):
    __tablename__ = "crm_file_access_events"
    __table_args__ = (
        CheckConstraint(
            "event_type = 'download_url_issued'",
            name="crm_file_access_event_type_valid",
        ),
        CheckConstraint(
            "expires_at > occurred_at",
            name="crm_file_access_event_expiry_valid",
        ),
    )

    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("crm_file_attachments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
