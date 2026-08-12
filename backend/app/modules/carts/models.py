from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin

CART_CUSTOMIZATION_TYPE = JSON().with_variant(JSONB, "postgresql")


class Cart(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "carts"
    __table_args__ = (
        CheckConstraint("length(token_digest_sha256) = 64", name="cart_token_digest_length"),
        CheckConstraint("client_updated_at_ms >= 0", name="cart_client_updated_nonnegative"),
        CheckConstraint("version > 0", name="cart_version_positive"),
    )

    token_digest_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_updated_at_ms: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CartItem.sort_order",
    )


class CartItem(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "client_item_id", name="uq_cart_item_client_id"),
        UniqueConstraint("cart_id", "sort_order", name="uq_cart_item_sort_order"),
        CheckConstraint("product_id_snapshot > 0", name="cart_item_product_positive"),
        CheckConstraint("unit_price >= 0", name="cart_item_price_nonnegative"),
        CheckConstraint("quantity > 0", name="cart_item_quantity_positive"),
        CheckConstraint("sort_order >= 0", name="cart_item_sort_order_nonnegative"),
    )

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    product_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    image_url_snapshot: Mapped[str] = mapped_column(String(4096), nullable=False, default="")
    size_snapshot: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    color_snapshot: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    customization_snapshot: Mapped[dict[str, object] | None] = mapped_column(
        CART_CUSTOMIZATION_TYPE,
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="items")


class CartMigrationRun(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "cart_migration_runs"
    __table_args__ = (
        CheckConstraint("length(fingerprint_sha256) = 64", name="cart_run_fingerprint_length"),
        CheckConstraint("carts_count >= 0", name="cart_run_carts_nonnegative"),
        CheckConstraint("items_count >= 0", name="cart_run_items_nonnegative"),
    )

    fingerprint_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    carts_count: Mapped[int] = mapped_column(Integer, nullable=False)
    items_count: Mapped[int] = mapped_column(Integer, nullable=False)
