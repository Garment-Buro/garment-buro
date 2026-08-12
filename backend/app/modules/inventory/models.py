from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class InventoryReservationStatus(str, Enum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    EXPIRED = "expired"


class InventoryReservation(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        UniqueConstraint("order_item_id", name="uq_inventory_reservation_order_item"),
        CheckConstraint("quantity > 0", name="inventory_reservation_quantity_positive"),
        CheckConstraint(
            "product_id_snapshot > 0",
            name="inventory_reservation_product_positive",
        ),
        CheckConstraint(
            "variant_id_snapshot IS NULL OR variant_id_snapshot > 0",
            name="inventory_reservation_variant_positive",
        ),
        CheckConstraint(
            "status IN ('active', 'confirmed', 'released', 'expired')",
            name="inventory_reservation_status_valid",
        ),
        CheckConstraint("version > 0", name="inventory_reservation_version_positive"),
        CheckConstraint(
            "(status = 'active' AND resolved_at IS NULL AND resolution_reason IS NULL) OR "
            "(status <> 'active' AND resolved_at IS NOT NULL "
            "AND resolution_reason IS NOT NULL)",
            name="inventory_reservation_resolution_consistent",
        ),
        Index(
            "ix_inventory_reservations_active_expiry",
            "status",
            "expires_at",
        ),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    variant_id_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=InventoryReservationStatus.ACTIVE.value,
        server_default=InventoryReservationStatus.ACTIVE.value,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolution_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
