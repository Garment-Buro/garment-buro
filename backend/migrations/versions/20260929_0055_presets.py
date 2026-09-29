"""Preset sources, search tags and shared fabric checkout holds."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260929_0055"
down_revision = "20260925_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("preset_source", sa.String(32), nullable=False, server_default="garment_buro"),
    )
    op.add_column(
        "products",
        sa.Column(
            "tags",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "inventory_reservations",
        sa.Column("stock_source", sa.String(16), nullable=False, server_default="product"),
    )
    op.create_table(
        "inventory_fabric_holds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reservation_id",
            sa.Integer(),
            sa.ForeignKey("inventory_reservations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "fabric_id",
            sa.Integer(),
            sa.ForeignKey("crm_fabrics.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requested_meters", sa.Numeric(14, 3), nullable=False),
        sa.Column("remaining_meters", sa.Numeric(14, 3), nullable=False),
        sa.UniqueConstraint("reservation_id", "fabric_id", name="uq_inventory_fabric_hold"),
        sa.CheckConstraint(
            "requested_meters > 0",
            name=op.f("ck_inventory_fabric_holds_fabric_hold_requested_positive"),
        ),
        sa.CheckConstraint(
            "remaining_meters >= 0 AND remaining_meters <= requested_meters",
            name=op.f("ck_inventory_fabric_holds_fabric_hold_remaining_valid"),
        ),
    )
    op.create_index(
        "ix_inventory_fabric_holds_reservation_id", "inventory_fabric_holds", ["reservation_id"]
    )
    op.create_index("ix_inventory_fabric_holds_fabric_id", "inventory_fabric_holds", ["fabric_id"])


def downgrade() -> None:
    # Refuse to lose reservations still backing customer orders.
    if op.get_context().as_sql:
        op.execute("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM inventory_fabric_holds WHERE remaining_meters > 0) THEN
                    RAISE EXCEPTION 'Resolve fabric checkout holds before downgrading';
                END IF;
            END $$;
        """)
    elif op.get_bind().scalar(
        sa.text("SELECT count(*) FROM inventory_fabric_holds WHERE remaining_meters > 0")
    ):
        raise RuntimeError("Resolve fabric checkout holds before downgrading")
    op.drop_table("inventory_fabric_holds")
    op.drop_column("inventory_reservations", "stock_source")
    op.drop_column("products", "tags")
    op.drop_column("products", "preset_source")
