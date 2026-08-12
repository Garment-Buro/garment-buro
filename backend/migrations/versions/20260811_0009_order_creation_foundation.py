"""Add immutable orders and idempotent creation requests.

Revision ID: 20260811_0009
Revises: 20260811_0008
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0009"
down_revision: str | Sequence[str] | None = "20260811_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("patronymic", sa.String(length=255), nullable=True),
        sa.Column("delivery_city", sa.String(length=255), nullable=False),
        sa.Column("delivery_method", sa.String(length=64), nullable=False),
        sa.Column("delivery_address", sa.Text(), nullable=False),
        sa.Column("cdek_point_code", sa.String(length=64), nullable=True),
        sa.Column("payment_method", sa.String(length=64), nullable=False),
        sa.Column("items_subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("delivery_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="RUB", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="new", nullable=False),
        sa.Column(
            "payment_status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("request_fingerprint_sha256", sa.String(length=64), nullable=False),
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
        sa.CheckConstraint("currency = 'RUB'", name=op.f("ck_orders_order_currency_rub")),
        sa.CheckConstraint(
            "delivery_price >= 0",
            name=op.f("ck_orders_order_delivery_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "items_subtotal >= 0",
            name=op.f("ck_orders_order_items_subtotal_nonnegative"),
        ),
        sa.CheckConstraint(
            "payment_status IN ('pending', 'paid', 'failed')",
            name=op.f("ck_orders_order_payment_status_valid"),
        ),
        sa.CheckConstraint(
            "length(request_fingerprint_sha256) = 64",
            name=op.f("ck_orders_order_request_fingerprint_length"),
        ),
        sa.CheckConstraint(
            "status IN ('new', 'processing', 'shipped', 'completed', 'cancelled')",
            name=op.f("ck_orders_order_status_valid"),
        ),
        sa.CheckConstraint(
            "total_price = items_subtotal + delivery_price",
            name=op.f("ck_orders_order_total_consistent"),
        ),
        sa.CheckConstraint(
            "total_price >= 0",
            name=op.f("ck_orders_order_total_price_nonnegative"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_orders_order_version_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_orders_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
    )
    op.create_index(op.f("ix_orders_email_normalized"), "orders", ["email_normalized"])
    op.create_index(op.f("ix_orders_created_at"), "orders", ["created_at"])
    op.create_index(op.f("ix_orders_payment_status"), "orders", ["payment_status"])
    op.create_index(op.f("ix_orders_phone"), "orders", ["phone"])
    op.create_index(op.f("ix_orders_status"), "orders", ["status"])
    op.create_index(op.f("ix_orders_user_id"), "orders", ["user_id"])

    op.create_table(
        "order_items",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("client_item_id", sa.String(length=255), nullable=False),
        sa.Column("product_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("variant_id_snapshot", sa.Integer(), nullable=True),
        sa.Column("sku_snapshot", sa.String(length=100), nullable=True),
        sa.Column("title_snapshot", sa.String(length=255), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("image_url_snapshot", sa.String(length=4096), nullable=False),
        sa.Column("size_snapshot", sa.String(length=32), nullable=False),
        sa.Column("color_snapshot", sa.String(length=64), nullable=False),
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
        sa.CheckConstraint(
            "line_total = unit_price * quantity",
            name=op.f("ck_order_items_order_item_line_total_consistent"),
        ),
        sa.CheckConstraint(
            "line_total >= 0",
            name=op.f("ck_order_items_order_item_line_total_nonnegative"),
        ),
        sa.CheckConstraint(
            "product_id_snapshot > 0",
            name=op.f("ck_order_items_order_item_product_positive"),
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_order_items_order_item_quantity_positive"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_order_items_order_item_sort_order_nonnegative"),
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name=op.f("ck_order_items_order_item_unit_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "variant_id_snapshot IS NULL OR variant_id_snapshot > 0",
            name=op.f("ck_order_items_order_item_variant_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.UniqueConstraint("order_id", "client_item_id", name="uq_order_item_client_id"),
        sa.UniqueConstraint("order_id", "sort_order", name="uq_order_item_sort_order"),
    )
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"])
    op.create_index(
        op.f("ix_order_items_product_id_snapshot"),
        "order_items",
        ["product_id_snapshot"],
    )
    op.create_index(
        op.f("ix_order_items_variant_id_snapshot"),
        "order_items",
        ["variant_id_snapshot"],
    )

    op.create_table(
        "order_status_history",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('new', 'processing', 'shipped', 'completed', 'cancelled')",
            name=op.f("ck_order_status_history_order_status_history_from_valid"),
        ),
        sa.CheckConstraint(
            "to_status IN ('new', 'processing', 'shipped', 'completed', 'cancelled')",
            name=op.f("ck_order_status_history_order_status_history_to_valid"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_order_status_history_order_status_history_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_order_status_history_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_status_history_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_status_history")),
        sa.UniqueConstraint("order_id", "version", name="uq_order_status_history_version"),
    )
    op.create_index(
        op.f("ix_order_status_history_actor_user_id"),
        "order_status_history",
        ["actor_user_id"],
    )
    op.create_index(
        op.f("ix_order_status_history_order_id"),
        "order_status_history",
        ["order_id"],
    )
    op.create_index(
        op.f("ix_order_status_history_to_status"),
        "order_status_history",
        ["to_status"],
    )

    op.create_table(
        "order_creation_requests",
        sa.Column("key_digest_sha256", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
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
            "length(key_digest_sha256) = 64",
            name=op.f("ck_order_creation_requests_order_creation_key_digest_length"),
        ),
        sa.CheckConstraint(
            "length(request_fingerprint_sha256) = 64",
            name=op.f("ck_order_creation_requests_order_creation_request_fingerprint_length"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_creation_requests_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_creation_requests")),
        sa.UniqueConstraint(
            "key_digest_sha256",
            name=op.f("uq_order_creation_requests_key_digest_sha256"),
        ),
        sa.UniqueConstraint("order_id", name=op.f("uq_order_creation_requests_order_id")),
    )
    op.create_index(
        op.f("ix_order_creation_requests_key_digest_sha256"),
        "order_creation_requests",
        ["key_digest_sha256"],
    )
    op.create_index(
        op.f("ix_order_creation_requests_order_id"),
        "order_creation_requests",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_order_creation_requests_order_id"),
        table_name="order_creation_requests",
    )
    op.drop_index(
        op.f("ix_order_creation_requests_key_digest_sha256"),
        table_name="order_creation_requests",
    )
    op.drop_table("order_creation_requests")
    op.drop_index(
        op.f("ix_order_status_history_to_status"),
        table_name="order_status_history",
    )
    op.drop_index(
        op.f("ix_order_status_history_order_id"),
        table_name="order_status_history",
    )
    op.drop_index(
        op.f("ix_order_status_history_actor_user_id"),
        table_name="order_status_history",
    )
    op.drop_table("order_status_history")
    op.drop_index(
        op.f("ix_order_items_variant_id_snapshot"),
        table_name="order_items",
    )
    op.drop_index(
        op.f("ix_order_items_product_id_snapshot"),
        table_name="order_items",
    )
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_table("order_items")
    op.drop_index(op.f("ix_orders_user_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_phone"), table_name="orders")
    op.drop_index(op.f("ix_orders_payment_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_email_normalized"), table_name="orders")
    op.drop_index(op.f("ix_orders_created_at"), table_name="orders")
    op.drop_table("orders")
