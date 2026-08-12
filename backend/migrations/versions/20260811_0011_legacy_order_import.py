"""Add deterministic legacy order import evidence.

Revision ID: 20260811_0011
Revises: 20260811_0010
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0011"
down_revision: str | Sequence[str] | None = "20260811_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column_name, existing_type in (
        ("email", sa.String(length=320)),
        ("email_normalized", sa.String(length=320)),
        ("phone", sa.String(length=64)),
        ("first_name", sa.String(length=255)),
        ("delivery_city", sa.String(length=255)),
        ("delivery_method", sa.String(length=64)),
        ("delivery_address", sa.Text()),
        ("payment_method", sa.String(length=64)),
    ):
        op.alter_column(
            "orders",
            column_name,
            existing_type=existing_type,
            nullable=True,
        )

    op.create_table(
        "legacy_order_imports",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("source_order_id", sa.Integer(), nullable=False),
        sa.Column("source_row_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_cart_items", sa.Text(), nullable=False),
        sa.Column("legacy_total_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("legacy_status", sa.String(length=64), nullable=True),
        sa.Column("legacy_payment_status", sa.String(length=64), nullable=True),
        sa.Column("payment_provider_id", sa.String(length=255), nullable=True),
        sa.Column("delivery_provider_uuid", sa.String(length=255), nullable=True),
        sa.Column("delivery_provider_number", sa.String(length=255), nullable=True),
        sa.Column("delivery_provider_status", sa.String(length=255), nullable=True),
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
            "source_order_id > 0",
            name=op.f("ck_legacy_order_imports_legacy_order_import_source_positive"),
        ),
        sa.CheckConstraint(
            "length(source_row_sha256) = 64",
            name=op.f("ck_legacy_order_imports_legacy_order_import_source_digest_length"),
        ),
        sa.CheckConstraint(
            "legacy_total_price >= 0",
            name=op.f("ck_legacy_order_imports_legacy_order_import_total_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_legacy_order_imports_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legacy_order_imports")),
        sa.UniqueConstraint("order_id", name=op.f("uq_legacy_order_imports_order_id")),
        sa.UniqueConstraint(
            "source_order_id",
            name=op.f("uq_legacy_order_imports_source_order_id"),
        ),
        sa.UniqueConstraint(
            "source_row_sha256",
            name=op.f("uq_legacy_order_imports_source_row_sha256"),
        ),
    )
    op.create_index(
        op.f("ix_legacy_order_imports_order_id"),
        "legacy_order_imports",
        ["order_id"],
    )
    op.create_index(
        op.f("ix_legacy_order_imports_source_order_id"),
        "legacy_order_imports",
        ["source_order_id"],
    )

    op.create_table(
        "order_migration_runs",
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("orders_count", sa.Integer(), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
        sa.Column("payment_references_count", sa.Integer(), nullable=False),
        sa.Column("delivery_references_count", sa.Integer(), nullable=False),
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
            "delivery_references_count >= 0",
            name=op.f("ck_order_migration_runs_order_migration_run_delivery_refs_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(fingerprint_sha256) = 64",
            name=op.f("ck_order_migration_runs_order_migration_run_fingerprint_length"),
        ),
        sa.CheckConstraint(
            "items_count >= 0",
            name=op.f("ck_order_migration_runs_order_migration_run_items_nonnegative"),
        ),
        sa.CheckConstraint(
            "orders_count >= 0",
            name=op.f("ck_order_migration_runs_order_migration_run_orders_nonnegative"),
        ),
        sa.CheckConstraint(
            "payment_references_count >= 0",
            name=op.f("ck_order_migration_runs_order_migration_run_payment_refs_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_migration_runs")),
        sa.UniqueConstraint(
            "fingerprint_sha256",
            name=op.f("uq_order_migration_runs_fingerprint_sha256"),
        ),
    )


def downgrade() -> None:
    op.drop_table("order_migration_runs")
    op.drop_index(
        op.f("ix_legacy_order_imports_source_order_id"),
        table_name="legacy_order_imports",
    )
    op.drop_index(
        op.f("ix_legacy_order_imports_order_id"),
        table_name="legacy_order_imports",
    )
    op.drop_table("legacy_order_imports")

    for column_name, existing_type in (
        ("payment_method", sa.String(length=64)),
        ("delivery_address", sa.Text()),
        ("delivery_method", sa.String(length=64)),
        ("delivery_city", sa.String(length=255)),
        ("first_name", sa.String(length=255)),
        ("phone", sa.String(length=64)),
        ("email_normalized", sa.String(length=320)),
        ("email", sa.String(length=320)),
    ):
        op.alter_column(
            "orders",
            column_name,
            existing_type=existing_type,
            nullable=False,
        )
