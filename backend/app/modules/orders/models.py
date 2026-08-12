from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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


class LegacyOrderClaimSource(str, Enum):
    VERIFIED_EMAIL = "verified_email"


class OrderStatus(str, Enum):
    NEW = "new"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderPaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


ORDER_CUSTOMIZATION_TYPE = JSON().with_variant(JSONB, "postgresql")
ORDER_HISTORY_DETAILS_TYPE = JSON().with_variant(JSONB, "postgresql")


class Order(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'processing', 'shipped', 'completed', 'cancelled')",
            name="order_status_valid",
        ),
        CheckConstraint(
            "payment_status IN ('pending', 'paid', 'failed')",
            name="order_payment_status_valid",
        ),
        CheckConstraint("currency = 'RUB'", name="order_currency_rub"),
        CheckConstraint("items_subtotal >= 0", name="order_items_subtotal_nonnegative"),
        CheckConstraint("delivery_price >= 0", name="order_delivery_price_nonnegative"),
        CheckConstraint("total_price >= 0", name="order_total_price_nonnegative"),
        CheckConstraint(
            "total_price = items_subtotal + delivery_price",
            name="order_total_consistent",
        ),
        CheckConstraint("version > 0", name="order_version_positive"),
        CheckConstraint(
            "length(request_fingerprint_sha256) = 64",
            name="order_request_fingerprint_length",
        ),
        Index("ix_orders_created_at", "created_at"),
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_normalized: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    patronymic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    cdek_point_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    items_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    delivery_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default="RUB",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OrderStatus.NEW.value,
        server_default=OrderStatus.NEW.value,
        index=True,
    )
    payment_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OrderPaymentStatus.PENDING.value,
        server_default=OrderPaymentStatus.PENDING.value,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    request_fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        order_by="OrderItem.sort_order",
    )
    status_history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order",
        order_by="OrderStatusHistory.version",
    )
    legacy_import: Mapped[LegacyOrderImport | None] = relationship(
        back_populates="order",
        uselist=False,
    )
    guest_access: Mapped[OrderGuestAccess | None] = relationship(
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OrderItem(Base, IntegerIdMixin):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "client_item_id", name="uq_order_item_client_id"),
        UniqueConstraint("order_id", "sort_order", name="uq_order_item_sort_order"),
        CheckConstraint("product_id_snapshot > 0", name="order_item_product_positive"),
        CheckConstraint(
            "variant_id_snapshot IS NULL OR variant_id_snapshot > 0",
            name="order_item_variant_positive",
        ),
        CheckConstraint("unit_price >= 0", name="order_item_unit_price_nonnegative"),
        CheckConstraint("quantity > 0", name="order_item_quantity_positive"),
        CheckConstraint("line_total >= 0", name="order_item_line_total_nonnegative"),
        CheckConstraint(
            "line_total = unit_price * quantity",
            name="order_item_line_total_consistent",
        ),
        CheckConstraint("sort_order >= 0", name="order_item_sort_order_nonnegative"),
        CheckConstraint(
            "(delivery_weight_kg_snapshot IS NULL "
            "AND delivery_height_cm_snapshot IS NULL "
            "AND delivery_width_cm_snapshot IS NULL "
            "AND delivery_length_cm_snapshot IS NULL) OR "
            "(delivery_weight_kg_snapshot > 0 "
            "AND delivery_height_cm_snapshot > 0 "
            "AND delivery_width_cm_snapshot > 0 "
            "AND delivery_length_cm_snapshot > 0)",
            name="order_item_delivery_measurements_complete",
        ),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    client_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    product_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    variant_id_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    image_url_snapshot: Mapped[str] = mapped_column(String(4096), nullable=False, default="")
    size_snapshot: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    color_snapshot: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    customization_snapshot: Mapped[dict[str, object] | None] = mapped_column(
        ORDER_CUSTOMIZATION_TYPE,
        nullable=True,
    )
    delivery_weight_kg_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )
    delivery_height_cm_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    delivery_width_cm_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    delivery_length_cm_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusHistory(Base, IntegerIdMixin):
    __tablename__ = "order_status_history"
    __table_args__ = (
        UniqueConstraint("order_id", "version", name="uq_order_status_history_version"),
        CheckConstraint("version > 0", name="order_status_history_version_positive"),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('new', 'processing', 'shipped', 'completed', 'cancelled')",
            name="order_status_history_from_valid",
        ),
        CheckConstraint(
            "to_status IN ('new', 'processing', 'shipped', 'completed', 'cancelled')",
            name="order_status_history_to_valid",
        ),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details: Mapped[dict[str, object]] = mapped_column(
        ORDER_HISTORY_DETAILS_TYPE,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    order: Mapped[Order] = relationship(back_populates="status_history")


class OrderCreationRequest(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "order_creation_requests"
    __table_args__ = (
        CheckConstraint(
            "length(key_digest_sha256) = 64",
            name="order_creation_key_digest_length",
        ),
        CheckConstraint(
            "length(request_fingerprint_sha256) = 64",
            name="order_creation_request_fingerprint_length",
        ),
    )

    key_digest_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    request_fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
        index=True,
    )


class LegacyOrderImport(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "legacy_order_imports"
    __table_args__ = (
        CheckConstraint("source_order_id > 0", name="legacy_order_import_source_positive"),
        CheckConstraint(
            "length(source_row_sha256) = 64",
            name="legacy_order_import_source_digest_length",
        ),
        CheckConstraint(
            "legacy_total_price >= 0",
            name="legacy_order_import_total_nonnegative",
        ),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    source_order_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
    )
    source_row_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    raw_cart_items: Mapped[str] = mapped_column(Text, nullable=False)
    legacy_total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    legacy_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    legacy_payment_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_provider_uuid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_provider_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_provider_status: Mapped[str | None] = mapped_column(String(255), nullable=True)

    order: Mapped[Order] = relationship(back_populates="legacy_import")


class OrderMigrationRun(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "order_migration_runs"
    __table_args__ = (
        CheckConstraint(
            "length(fingerprint_sha256) = 64",
            name="order_migration_run_fingerprint_length",
        ),
        CheckConstraint("orders_count >= 0", name="order_migration_run_orders_nonnegative"),
        CheckConstraint("items_count >= 0", name="order_migration_run_items_nonnegative"),
        CheckConstraint(
            "payment_references_count >= 0",
            name="order_migration_run_payment_refs_nonnegative",
        ),
        CheckConstraint(
            "delivery_references_count >= 0",
            name="order_migration_run_delivery_refs_nonnegative",
        ),
    )

    fingerprint_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False)
    items_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_references_count: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_references_count: Mapped[int] = mapped_column(Integer, nullable=False)


class OrderGuestAccess(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "order_guest_access"
    __table_args__ = (
        CheckConstraint(
            "length(token_digest_sha256) = 64",
            name="order_guest_access_token_digest_length",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="order_guest_access_expiry_after_creation",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="order_guest_access_revocation_after_creation",
        ),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    token_digest_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    order: Mapped[Order] = relationship(back_populates="guest_access")


class LegacyOrderClaim(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "legacy_order_claims"
    __table_args__ = (
        UniqueConstraint(
            "legacy_order_id",
            name="uq_legacy_order_claim_legacy_order_id",
        ),
        CheckConstraint(
            "legacy_order_id > 0",
            name="legacy_order_claim_order_id_positive",
        ),
        CheckConstraint(
            "source IN ('verified_email')",
            name="legacy_order_claim_source_valid",
        ),
        CheckConstraint(
            "length(identifier_digest) = 64",
            name="legacy_order_claim_identifier_digest_length",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    legacy_order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    identifier_digest: Mapped[str] = mapped_column(String(64), nullable=False)
