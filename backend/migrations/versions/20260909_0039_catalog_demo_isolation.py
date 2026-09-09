"""Keep production demos outside the reviewed storefront catalog."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0039"
down_revision = "20260909_0038"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text("UPDATE products SET is_demo = true WHERE slug = 'production-demo-hoodie-v1'")
    )


def downgrade():
    op.drop_column("products", "is_demo")
