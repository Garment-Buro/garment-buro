"""Ordered partial indexes for paginated public product cards."""

import sqlalchemy as sa
from alembic import op

revision = "20261013_0058"
down_revision = "20261013_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    public = sa.text("is_active IS TRUE AND is_demo IS FALSE")
    op.create_index(
        "ix_products_public_recent",
        "products",
        [sa.text("created_at DESC"), sa.text("id DESC")],
        postgresql_where=public,
        sqlite_where=public,
    )
    op.create_index(
        "ix_products_public_price_cheap",
        "products",
        ["price", sa.text("id DESC")],
        postgresql_where=public,
        sqlite_where=public,
    )
    op.create_index(
        "ix_products_public_price_expensive",
        "products",
        [sa.text("price DESC"), sa.text("id DESC")],
        postgresql_where=public,
        sqlite_where=public,
    )


def downgrade() -> None:
    op.drop_index("ix_products_public_price_expensive", table_name="products")
    op.drop_index("ix_products_public_price_cheap", table_name="products")
    op.drop_index("ix_products_public_recent", table_name="products")
