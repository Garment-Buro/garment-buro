"""Name continuations of model and product categories.

Revision ID: 20261019_0074
Revises: 20261019_0073
"""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0074"
down_revision = "20261019_0073"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_crm_model_categories_directory_name", "crm_garment_model_categories"),
    ("ix_product_categories_directory_name", "product_categories"),
)


def upgrade() -> None:
    collation = '::text COLLATE "pg_c_utf8"' if op.get_bind().dialect.name == "postgresql" else ""
    for name, table in INDEXES:
        op.create_index(name, table, [sa.text(f"lower(name{collation})"), "id"])


def downgrade() -> None:
    for name, table in reversed(INDEXES):
        op.drop_index(name, table_name=table)
