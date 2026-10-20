from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class CustomerProject(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "customer_projects"
    __table_args__ = (
        UniqueConstraint("user_id", "client_key", name="uq_customer_projects_user_client_key"),
        CheckConstraint("kind IN ('draft', 'collection')", name="customer_project_kind_valid"),
        CheckConstraint("version > 0", name="customer_project_version_positive"),
        CheckConstraint("length(creation_sha256) = 64", name="customer_project_creation_hash"),
        CheckConstraint(
            "deleted_at IS NOT NULL OR snapshot IS NOT NULL",
            name="customer_project_document_required",
        ),
        Index(
            "ix_customer_projects_user_kind_recent",
            "user_id",
            "kind",
            "id",
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    client_key: Mapped[str] = mapped_column(String(100), nullable=False)
    creation_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    snapshot: Mapped[dict | None] = mapped_column(
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomerProjectMedia(Base):
    __tablename__ = "customer_project_media"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("customer_projects.id", ondelete="CASCADE"), primary_key=True
    )
    media_object_id: Mapped[int] = mapped_column(
        ForeignKey("media_objects.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
