"""Add transactional inventory reservations.

Revision ID: 20260811_0010
Revises: 20260811_0009
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0010"
down_revision: str | Sequence[str] | None = "20260811_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("reserved_quantity", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_products_product_reserved_quantity_nonnegative"),
        "products",
        "reserved_quantity >= 0",
    )
    op.create_check_constraint(
        op.f("ck_products_product_reserved_not_above_stock"),
        "products",
        "reserved_quantity <= stock_quantity",
    )

    op.add_column(
        "product_variants",
        sa.Column("reserved_quantity", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_product_variants_product_variant_reserved_quantity_nonnegative"),
        "product_variants",
        "reserved_quantity >= 0",
    )
    op.create_check_constraint(
        op.f("ck_product_variants_product_variant_reserved_not_above_stock"),
        "product_variants",
        "reserved_quantity <= stock_quantity",
    )

    op.create_table(
        "inventory_reservations",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("product_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("variant_id_snapshot", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="active",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_reason", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "product_id_snapshot > 0",
            name=op.f("ck_inventory_reservations_inventory_reservation_product_positive"),
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_inventory_reservations_inventory_reservation_quantity_positive"),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND resolved_at IS NULL AND resolution_reason IS NULL) OR "
            "(status <> 'active' AND resolved_at IS NOT NULL "
            "AND resolution_reason IS NOT NULL)",
            name=op.f("ck_inventory_reservations_inventory_reservation_resolution_consistent"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'confirmed', 'released', 'expired')",
            name=op.f("ck_inventory_reservations_inventory_reservation_status_valid"),
        ),
        sa.CheckConstraint(
            "variant_id_snapshot IS NULL OR variant_id_snapshot > 0",
            name=op.f("ck_inventory_reservations_inventory_reservation_variant_positive"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_inventory_reservations_inventory_reservation_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_inventory_reservations_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("fk_inventory_reservations_order_item_id_order_items"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_reservations")),
        sa.UniqueConstraint(
            "order_item_id",
            name="uq_inventory_reservation_order_item",
        ),
    )
    op.create_index(
        "ix_inventory_reservations_active_expiry",
        "inventory_reservations",
        ["status", "expires_at"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_expires_at"),
        "inventory_reservations",
        ["expires_at"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_order_id"),
        "inventory_reservations",
        ["order_id"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_order_item_id"),
        "inventory_reservations",
        ["order_item_id"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_product_id_snapshot"),
        "inventory_reservations",
        ["product_id_snapshot"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_status"),
        "inventory_reservations",
        ["status"],
    )
    op.create_index(
        op.f("ix_inventory_reservations_variant_id_snapshot"),
        "inventory_reservations",
        ["variant_id_snapshot"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_inventory_reservations_variant_id_snapshot"),
        table_name="inventory_reservations",
    )
    op.drop_index(
        op.f("ix_inventory_reservations_status"),
        table_name="inventory_reservations",
    )
    op.drop_index(
        op.f("ix_inventory_reservations_product_id_snapshot"),
        table_name="inventory_reservations",
    )
    op.drop_index(
        op.f("ix_inventory_reservations_order_item_id"),
        table_name="inventory_reservations",
    )
    op.drop_index(
        op.f("ix_inventory_reservations_order_id"),
        table_name="inventory_reservations",
    )
    op.drop_index(
        "ix_inventory_reservations_active_expiry",
        table_name="inventory_reservations",
    )
    op.drop_index(
        op.f("ix_inventory_reservations_expires_at"),
        table_name="inventory_reservations",
    )
    op.drop_table("inventory_reservations")

    op.drop_constraint(
        op.f("ck_product_variants_product_variant_reserved_not_above_stock"),
        "product_variants",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_product_variants_product_variant_reserved_quantity_nonnegative"),
        "product_variants",
        type_="check",
    )
    op.drop_column("product_variants", "reserved_quantity")

    op.drop_constraint(
        op.f("ck_products_product_reserved_not_above_stock"),
        "products",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_products_product_reserved_quantity_nonnegative"),
        "products",
        type_="check",
    )
    op.drop_column("products", "reserved_quantity")
