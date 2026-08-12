from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.modules.media.models import ProductMedia, ProductVariantMedia

STRING_LIST_TYPE = JSON().with_variant(JSONB, "postgresql")
CATALOG_AUDIT_DETAILS_TYPE = JSON().with_variant(JSONB, "postgresql")
CATALOG_DOCUMENT_TYPE = JSON().with_variant(JSONB, "postgresql")


class Product(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="product_title_nonempty"),
        CheckConstraint("price >= 0", name="product_price_nonnegative"),
        CheckConstraint(
            "old_price IS NULL OR old_price >= 0",
            name="product_old_price_nonnegative",
        ),
        CheckConstraint(
            "stock_quantity >= 0",
            name="product_stock_quantity_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="product_reserved_quantity_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity <= stock_quantity",
            name="product_reserved_not_above_stock",
        ),
        CheckConstraint("weight_kg >= 0", name="product_weight_nonnegative"),
        CheckConstraint("height_cm >= 0", name="product_height_nonnegative"),
        CheckConstraint("width_cm >= 0", name="product_width_nonnegative"),
        CheckConstraint("length_cm >= 0", name="product_length_nonnegative"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    composition: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    sizes: Mapped[list[str]] = mapped_column(
        STRING_LIST_TYPE,
        nullable=False,
        default=lambda: ["S", "M", "L", "XL"],
    )
    colors: Mapped[list[str]] = mapped_column(
        STRING_LIST_TYPE,
        nullable=False,
        default=lambda: ["black", "white"],
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    product_type: Mapped[str] = mapped_column(
        "type",
        String(64),
        nullable=False,
        default="normal",
        server_default="normal",
    )
    weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
        default=0,
        server_default="0",
    )
    height_cm: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    width_cm: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    length_cm: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    reserved_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProductVariant.id",
    )
    media_links: Mapped[list[ProductMedia]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProductMedia.sort_order",
    )


class ProductVariant(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "size",
            "color",
            name="uq_product_variant_identity",
        ),
        CheckConstraint(
            "stock_quantity >= 0",
            name="product_variant_stock_quantity_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="product_variant_reserved_quantity_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity <= stock_quantity",
            name="product_variant_reserved_not_above_stock",
        ),
        CheckConstraint(
            "width_cm IS NULL OR width_cm >= 0",
            name="product_variant_width_nonnegative",
        ),
        CheckConstraint(
            "height_cm IS NULL OR height_cm >= 0",
            name="product_variant_height_nonnegative",
        ),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    size: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    color: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    reserved_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    width_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    product: Mapped[Product] = relationship(back_populates="variants")
    media_links: Mapped[list[ProductVariantMedia]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProductVariantMedia.sort_order",
    )


class CatalogMigrationRun(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "catalog_migration_runs"
    __table_args__ = (
        CheckConstraint("products_count >= 0", name="catalog_run_products_nonnegative"),
        CheckConstraint("variants_count >= 0", name="catalog_run_variants_nonnegative"),
        CheckConstraint("media_count >= 0", name="catalog_run_media_nonnegative"),
        CheckConstraint(
            "media_references_count >= 0",
            name="catalog_run_media_references_nonnegative",
        ),
        CheckConstraint(
            "length(fingerprint_sha256) = 64",
            name="catalog_run_fingerprint_length",
        ),
    )

    fingerprint_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    products_count: Mapped[int] = mapped_column(Integer, nullable=False)
    variants_count: Mapped[int] = mapped_column(Integer, nullable=False)
    media_count: Mapped[int] = mapped_column(Integer, nullable=False)
    media_references_count: Mapped[int] = mapped_column(Integer, nullable=False)


class CatalogAuditEvent(Base, IntegerIdMixin):
    __tablename__ = "catalog_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('product.created', 'product.updated', 'product.deleted')",
            name="catalog_audit_action_valid",
        ),
        CheckConstraint(
            "length(snapshot_checksum_sha256) = 64",
            name="catalog_audit_snapshot_checksum_length",
        ),
    )

    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snapshot_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(
        CATALOG_AUDIT_DETAILS_TYPE,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class CatalogDocument(Base, TimestampMixin):
    __tablename__ = "catalog_documents"
    __table_args__ = (
        CheckConstraint(
            "document_key IN ('settings', 'options')",
            name="catalog_document_key_valid",
        ),
        CheckConstraint("version > 0", name="catalog_document_version_positive"),
    )

    document_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    payload: Mapped[dict[str, object]] = mapped_column(CATALOG_DOCUMENT_TYPE, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class CatalogDocumentRevision(Base, IntegerIdMixin):
    __tablename__ = "catalog_document_revisions"
    __table_args__ = (
        UniqueConstraint(
            "document_key",
            "version",
            name="uq_catalog_document_revision_key_version",
        ),
        CheckConstraint(
            "document_key IN ('settings', 'options')",
            name="catalog_document_revision_key_valid",
        ),
        CheckConstraint("version > 0", name="catalog_document_revision_version_positive"),
    )

    document_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(CATALOG_DOCUMENT_TYPE, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class CatalogContentMigrationRun(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "catalog_content_migration_runs"
    __table_args__ = (
        CheckConstraint(
            "documents_count >= 0",
            name="catalog_content_run_documents_nonnegative",
        ),
        CheckConstraint(
            "length(fingerprint_sha256) = 64",
            name="catalog_content_run_fingerprint_length",
        ),
    )

    fingerprint_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    documents_count: Mapped[int] = mapped_column(Integer, nullable=False)
