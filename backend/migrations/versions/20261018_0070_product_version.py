"""Version catalog edits and physical stock changes.

Revision ID: 20261018_0070
Revises: 20261017_0069
"""

import sqlalchemy as sa
from alembic import op

revision = "20261018_0070"
down_revision = "20261017_0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    with op.batch_alter_table("products") as batch:
        batch.create_check_constraint("product_version_positive", "version > 0")


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("product_version_positive", type_="check")
        batch.drop_column("version")
