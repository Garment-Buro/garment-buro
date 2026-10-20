"""Version encrypted partner requisites without rewriting their payloads.

Revision ID: 20261018_0072
Revises: 20261018_0071
"""

import sqlalchemy as sa
from alembic import op

revision = "20261018_0072"
down_revision = "20261018_0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "partner_requisites", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    with op.batch_alter_table("partner_requisites") as batch:
        batch.create_check_constraint("partner_requisites_version_positive", "version > 0")


def downgrade() -> None:
    with op.batch_alter_table("partner_requisites") as batch:
        batch.drop_constraint("partner_requisites_version_positive", type_="check")
        batch.drop_column("version")
