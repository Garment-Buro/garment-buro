"""Seek the first bounded SKU page of a preset in ID order.

Revision ID: 20261019_0077
Revises: 20261019_0076
"""

from alembic import op

revision = "20261019_0077"
down_revision = "20261019_0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_product_variants_editor", "product_variants", ["product_id", "id"])
    op.drop_index("ix_product_variants_product_id", table_name="product_variants")


def downgrade() -> None:
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])
    op.drop_index("ix_product_variants_editor", table_name="product_variants")
