"""Versioned edits of existing partner landings.

Revision ID: 20261016_0065
Revises: 20261015_0064
"""

import sqlalchemy as sa
from alembic import op

revision = "20261016_0065"
down_revision = "20261015_0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_partner_landings_partner_id", table_name="partner_landings")
    op.create_index("ix_partner_landings_owner_recent", "partner_landings", ["partner_id", "id"])
    op.add_column(
        "partner_landings", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_check_constraint(
        op.f("ck_partner_landings_partner_landing_version_positive"),
        "partner_landings",
        "version > 0",
    )


def downgrade() -> None:
    op.drop_index("ix_partner_landings_owner_recent", table_name="partner_landings")
    op.create_index("ix_partner_landings_partner_id", "partner_landings", ["partner_id"])
    op.drop_constraint(
        op.f("ck_partner_landings_partner_landing_version_positive"),
        "partner_landings",
        type_="check",
    )
    op.drop_column("partner_landings", "version")
