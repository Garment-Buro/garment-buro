"""Check reserved SKUs without reading every unreserved variant.

Revision ID: 20261019_0078
Revises: 20261019_0077
"""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0078"
down_revision = "20261019_0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_product_variants_reserved_product",
        "product_variants",
        ["product_id", "id"],
        postgresql_where=sa.text("reserved_quantity > 0"),
        sqlite_where=sa.text("reserved_quantity > 0"),
    )


def downgrade() -> None:
    op.drop_index("ix_product_variants_reserved_product", table_name="product_variants")
