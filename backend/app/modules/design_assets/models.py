from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class DesignAsset(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "design_assets"
    __table_args__ = (
        CheckConstraint("length(access_digest_sha256) = 64", name="design_asset_digest_length"),
        Index("ix_design_assets_expiry", "expires_at", "id"),
    )

    media_object_id: Mapped[int] = mapped_column(
        ForeignKey("media_objects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    access_digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # NULL is permanent retention by an accepted order. Normal account deletion
    # preserves accounting orders; explicit order erasure must reconcile its files.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CartDesignAsset(Base):
    __tablename__ = "cart_design_assets"

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), primary_key=True
    )
    design_asset_id: Mapped[int] = mapped_column(
        ForeignKey("design_assets.id", ondelete="RESTRICT"), primary_key=True, index=True
    )


class OrderDesignAsset(Base):
    __tablename__ = "order_design_assets"

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True
    )
    design_asset_id: Mapped[int] = mapped_column(
        ForeignKey("design_assets.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
