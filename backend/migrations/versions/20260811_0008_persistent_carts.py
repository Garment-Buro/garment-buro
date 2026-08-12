"""Add persistent carts and normalized cart item snapshots.

Revision ID: 20260811_0008
Revises: 20260811_0007
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0008"
down_revision: str | Sequence[str] | None = "20260811_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carts",
        sa.Column("token_digest_sha256", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("client_updated_at_ms", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            "client_updated_at_ms >= 0",
            name=op.f("ck_carts_cart_client_updated_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(token_digest_sha256) = 64",
            name=op.f("ck_carts_cart_token_digest_length"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_carts_cart_version_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_carts_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_carts")),
        sa.UniqueConstraint("token_digest_sha256", name=op.f("uq_carts_token_digest_sha256")),
    )
    op.create_index(op.f("ix_carts_expires_at"), "carts", ["expires_at"])
    op.create_index(op.f("ix_carts_token_digest_sha256"), "carts", ["token_digest_sha256"])
    op.create_index(op.f("ix_carts_user_id"), "carts", ["user_id"])

    op.create_table(
        "cart_items",
        sa.Column("cart_id", sa.Integer(), nullable=False),
        sa.Column("client_item_id", sa.String(length=255), nullable=False),
        sa.Column("product_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("title_snapshot", sa.String(length=255), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("image_url_snapshot", sa.String(length=4096), nullable=False),
        sa.Column("size_snapshot", sa.String(length=32), nullable=False),
        sa.Column("color_snapshot", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "customization_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
            "unit_price >= 0",
            name=op.f("ck_cart_items_cart_item_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "product_id_snapshot > 0",
            name=op.f("ck_cart_items_cart_item_product_positive"),
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_cart_items_cart_item_quantity_positive"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_cart_items_cart_item_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["cart_id"],
            ["carts.id"],
            name=op.f("fk_cart_items_cart_id_carts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cart_items")),
        sa.UniqueConstraint("cart_id", "client_item_id", name="uq_cart_item_client_id"),
        sa.UniqueConstraint("cart_id", "sort_order", name="uq_cart_item_sort_order"),
    )
    op.create_index(op.f("ix_cart_items_cart_id"), "cart_items", ["cart_id"])
    op.create_index(
        op.f("ix_cart_items_product_id_snapshot"),
        "cart_items",
        ["product_id_snapshot"],
    )

    op.create_table(
        "cart_migration_runs",
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("carts_count", sa.Integer(), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
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
            "carts_count >= 0",
            name=op.f("ck_cart_migration_runs_cart_run_carts_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(fingerprint_sha256) = 64",
            name=op.f("ck_cart_migration_runs_cart_run_fingerprint_length"),
        ),
        sa.CheckConstraint(
            "items_count >= 0",
            name=op.f("ck_cart_migration_runs_cart_run_items_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cart_migration_runs")),
        sa.UniqueConstraint(
            "fingerprint_sha256",
            name=op.f("uq_cart_migration_runs_fingerprint_sha256"),
        ),
    )


def downgrade() -> None:
    op.drop_table("cart_migration_runs")
    op.drop_index(
        op.f("ix_cart_items_product_id_snapshot"),
        table_name="cart_items",
    )
    op.drop_index(op.f("ix_cart_items_cart_id"), table_name="cart_items")
    op.drop_table("cart_items")
    op.drop_index(op.f("ix_carts_user_id"), table_name="carts")
    op.drop_index(op.f("ix_carts_token_digest_sha256"), table_name="carts")
    op.drop_index(op.f("ix_carts_expires_at"), table_name="carts")
    op.drop_table("carts")
