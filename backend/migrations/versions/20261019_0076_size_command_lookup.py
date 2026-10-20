"""Cover ID lookup by the unique model/size code without a second heap read.

Revision ID: 20261019_0076
Revises: 20261019_0075
"""

from alembic import op

revision = "20261019_0076"
down_revision = "20261019_0075"
branch_labels = None
depends_on = None

TABLE = "crm_garment_sizes"
CONSTRAINT = "uq_crm_garment_size_code"


def upgrade() -> None:
    op.drop_index("ix_crm_garment_sizes_code", table_name=TABLE)
    op.drop_constraint(CONSTRAINT, TABLE, type_="unique")
    op.execute(
        "ALTER TABLE crm_garment_sizes ADD CONSTRAINT uq_crm_garment_size_code "
        "UNIQUE (garment_model_id, code) INCLUDE (id)"
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, TABLE, type_="unique")
    op.create_unique_constraint(CONSTRAINT, TABLE, ["garment_model_id", "code"])
    op.create_index("ix_crm_garment_sizes_code", TABLE, ["code"])
