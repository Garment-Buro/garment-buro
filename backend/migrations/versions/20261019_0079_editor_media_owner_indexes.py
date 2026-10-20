"""Use unique owner/role/order indexes instead of redundant owner-only indexes."""

from alembic import op

revision = "20261019_0079"
down_revision = "20261019_0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_product_media_product_id", table_name="product_media")
    op.drop_index("ix_product_variant_media_product_variant_id", table_name="product_variant_media")


def downgrade() -> None:
    op.create_index("ix_product_media_product_id", "product_media", ["product_id"])
    op.create_index(
        "ix_product_variant_media_product_variant_id",
        "product_variant_media",
        ["product_variant_id"],
    )
