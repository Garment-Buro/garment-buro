from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin


class CrmMaterialReservationStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class CrmMaterialMovementType(str, Enum):
    RECEIPT = "receipt"
    RESERVE = "reserve"
    RELEASE = "release"
    CONSUME = "consume"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"


class CrmMaterialBalance(Base):
    __tablename__ = "crm_material_balances"
    __table_args__ = (
        CheckConstraint("on_hand_meters >= 0", name="crm_material_balance_on_hand_nonnegative"),
        CheckConstraint("reserved_meters >= 0", name="crm_material_balance_reserved_nonnegative"),
        CheckConstraint(
            "reserved_meters <= on_hand_meters",
            name="crm_material_balance_reserved_not_above_on_hand",
        ),
        CheckConstraint("version > 0", name="crm_material_balance_version_positive"),
    )

    fabric_id: Mapped[int] = mapped_column(
        ForeignKey("crm_fabrics.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    on_hand_meters: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=0, server_default="0"
    )
    reserved_meters: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=0, server_default="0"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CrmMaterialReservation(Base, IntegerIdMixin):
    __tablename__ = "crm_material_reservations"
    __table_args__ = (
        UniqueConstraint(
            "production_plan_revision_id",
            "fabric_id",
            name="uq_crm_material_reservation_plan_fabric",
        ),
        CheckConstraint(
            "requested_meters > 0",
            name="crm_material_reservation_requested_positive",
        ),
        CheckConstraint(
            "remaining_meters >= 0 AND consumed_meters >= 0 AND released_meters >= 0",
            name="crm_material_reservation_quantities_nonnegative",
        ),
        CheckConstraint(
            "requested_meters = remaining_meters + consumed_meters + released_meters",
            name="crm_material_reservation_accounting_consistent",
        ),
        CheckConstraint(
            "(status = 'active' AND remaining_meters > 0) OR "
            "(status = 'closed' AND remaining_meters = 0)",
            name="crm_material_reservation_status_consistent",
        ),
        CheckConstraint("version > 0", name="crm_material_reservation_version_positive"),
    )

    production_plan_revision_id: Mapped[int] = mapped_column(
        ForeignKey("crm_production_plan_revisions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fabric_id: Mapped[int] = mapped_column(
        ForeignKey("crm_fabrics.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requested_meters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    remaining_meters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    consumed_meters: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=0, server_default="0"
    )
    released_meters: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CrmMaterialReservationStatus.ACTIVE.value,
        server_default=CrmMaterialReservationStatus.ACTIVE.value,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CrmMaterialMovement(Base, IntegerIdMixin):
    __tablename__ = "crm_material_movements"
    __table_args__ = (
        UniqueConstraint(
            "fabric_id",
            "idempotency_key_sha256",
            name="uq_crm_material_movement_fabric_key",
        ),
        CheckConstraint(
            "movement_type IN ('receipt', 'reserve', 'release', 'consume', "
            "'adjustment_in', 'adjustment_out')",
            name="crm_material_movement_type_valid",
        ),
        CheckConstraint("quantity_meters > 0", name="crm_material_movement_quantity_positive"),
        CheckConstraint(
            "balance_on_hand_after >= 0 AND balance_reserved_after >= 0 "
            "AND balance_reserved_after <= balance_on_hand_after",
            name="crm_material_movement_balance_valid",
        ),
        CheckConstraint(
            "length(idempotency_key_sha256) = 64 AND length(command_sha256) = 64",
            name="crm_material_movement_digests_valid",
        ),
        CheckConstraint(
            "(movement_type IN ('reserve', 'release', 'consume') "
            "AND reservation_id IS NOT NULL) OR "
            "(movement_type IN ('receipt', 'adjustment_in', 'adjustment_out') "
            "AND reservation_id IS NULL)",
            name="crm_material_movement_reservation_consistent",
        ),
    )

    fabric_id: Mapped[int] = mapped_column(
        ForeignKey("crm_fabrics.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reservation_id: Mapped[int | None] = mapped_column(
        ForeignKey("crm_material_reservations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    quantity_meters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    balance_on_hand_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    balance_reserved_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    idempotency_key_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    command_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
