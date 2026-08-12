"""Add normalized catalog and media metadata tables.

Revision ID: 20260811_0002
Revises: 20260811_0001
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0002"
down_revision: str | Sequence[str] | None = "20260811_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("old_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("composition", sa.Text(), nullable=True),
        sa.Column("model_info", sa.Text(), nullable=True),
        sa.Column("sizes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("colors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.String(length=64),
            server_default=sa.text("'normal'"),
            nullable=False,
        ),
        sa.Column(
            "weight_kg",
            sa.Numeric(precision=10, scale=3),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "height_cm",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "width_cm",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "length_cm",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "stock_quantity",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "height_cm >= 0",
            name=op.f("ck_products_product_height_nonnegative"),
        ),
        sa.CheckConstraint(
            "length_cm >= 0",
            name=op.f("ck_products_product_length_nonnegative"),
        ),
        sa.CheckConstraint(
            "old_price IS NULL OR old_price >= 0",
            name=op.f("ck_products_product_old_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "price >= 0",
            name=op.f("ck_products_product_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "stock_quantity >= 0",
            name=op.f("ck_products_product_stock_quantity_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0",
            name=op.f("ck_products_product_title_nonempty"),
        ),
        sa.CheckConstraint(
            "weight_kg >= 0",
            name=op.f("ck_products_product_weight_nonnegative"),
        ),
        sa.CheckConstraint(
            "width_cm >= 0",
            name=op.f("ck_products_product_width_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("slug", name=op.f("uq_products_slug")),
    )
    op.create_index(op.f("ix_products_title"), "products", ["title"], unique=False)

    op.create_table(
        "media_objects",
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default=sa.text("'minio'"),
            nullable=False,
        ),
        sa.Column("bucket_name", sa.String(length=63), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("etag", sa.String(length=128), nullable=True),
        sa.Column("version_id", sa.String(length=255), nullable=True),
        sa.Column(
            "is_public",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64",
            name=op.f("ck_media_objects_media_object_checksum_length"),
        ),
        sa.CheckConstraint(
            "size_bytes > 0",
            name=op.f("ck_media_objects_media_object_size_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed', 'deleted')",
            name=op.f("ck_media_objects_media_object_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_objects")),
        sa.UniqueConstraint(
            "bucket_name",
            "object_key",
            name="uq_media_object_bucket_key",
        ),
    )
    op.create_index(
        op.f("ix_media_objects_checksum_sha256"),
        "media_objects",
        ["checksum_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_media_objects_status"),
        "media_objects",
        ["status"],
        unique=False,
    )

    op.create_table(
        "product_variants",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("size", sa.String(length=32), nullable=True),
        sa.Column("color", sa.String(length=64), nullable=True),
        sa.Column("color_hex", sa.String(length=7), nullable=True),
        sa.Column(
            "stock_quantity",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("width_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("height_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "height_cm IS NULL OR height_cm >= 0",
            name=op.f("ck_product_variants_product_variant_height_nonnegative"),
        ),
        sa.CheckConstraint(
            "stock_quantity >= 0",
            name=op.f("ck_product_variants_product_variant_stock_quantity_nonnegative"),
        ),
        sa.CheckConstraint(
            "width_cm IS NULL OR width_cm >= 0",
            name=op.f("ck_product_variants_product_variant_width_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_variants_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_variants")),
        sa.UniqueConstraint(
            "product_id",
            "size",
            "color",
            name="uq_product_variant_identity",
        ),
        sa.UniqueConstraint("sku", name=op.f("uq_product_variants_sku")),
    )
    op.create_index(
        op.f("ix_product_variants_color"),
        "product_variants",
        ["color"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_variants_product_id"),
        "product_variants",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_variants_size"),
        "product_variants",
        ["size"],
        unique=False,
    )

    op.create_table(
        "product_media",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("media_object_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_product_media_product_media_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["media_object_id"],
            ["media_objects.id"],
            name=op.f("fk_product_media_media_object_id_media_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_media_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_media")),
        sa.UniqueConstraint(
            "product_id",
            "role",
            "sort_order",
            name="uq_product_media_role_order",
        ),
    )
    op.create_index(
        op.f("ix_product_media_media_object_id"),
        "product_media",
        ["media_object_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_media_product_id"),
        "product_media",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_media_role"),
        "product_media",
        ["role"],
        unique=False,
    )

    op.create_table(
        "product_variant_media",
        sa.Column("product_variant_id", sa.Integer(), nullable=False),
        sa.Column("media_object_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_product_variant_media_product_variant_media_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["media_object_id"],
            ["media_objects.id"],
            name=op.f("fk_product_variant_media_media_object_id_media_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_variant_id"],
            ["product_variants.id"],
            name=op.f("fk_product_variant_media_product_variant_id_product_variants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_variant_media")),
        sa.UniqueConstraint(
            "product_variant_id",
            "role",
            "sort_order",
            name="uq_product_variant_media_role_order",
        ),
    )
    op.create_index(
        op.f("ix_product_variant_media_media_object_id"),
        "product_variant_media",
        ["media_object_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_variant_media_product_variant_id"),
        "product_variant_media",
        ["product_variant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_variant_media_role"),
        "product_variant_media",
        ["role"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_product_variant_media_role"),
        table_name="product_variant_media",
    )
    op.drop_index(
        op.f("ix_product_variant_media_product_variant_id"),
        table_name="product_variant_media",
    )
    op.drop_index(
        op.f("ix_product_variant_media_media_object_id"),
        table_name="product_variant_media",
    )
    op.drop_table("product_variant_media")

    op.drop_index(op.f("ix_product_media_role"), table_name="product_media")
    op.drop_index(op.f("ix_product_media_product_id"), table_name="product_media")
    op.drop_index(
        op.f("ix_product_media_media_object_id"),
        table_name="product_media",
    )
    op.drop_table("product_media")

    op.drop_index(op.f("ix_product_variants_size"), table_name="product_variants")
    op.drop_index(
        op.f("ix_product_variants_product_id"),
        table_name="product_variants",
    )
    op.drop_index(op.f("ix_product_variants_color"), table_name="product_variants")
    op.drop_table("product_variants")

    op.drop_index(op.f("ix_media_objects_status"), table_name="media_objects")
    op.drop_index(
        op.f("ix_media_objects_checksum_sha256"),
        table_name="media_objects",
    )
    op.drop_table("media_objects")

    op.drop_index(op.f("ix_products_title"), table_name="products")
    op.drop_table("products")
