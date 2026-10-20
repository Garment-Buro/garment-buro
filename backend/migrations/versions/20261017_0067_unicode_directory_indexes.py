"""Unicode name ordering shared by public people and community keyset queries.

Revision ID: 20261017_0067
Revises: 20261017_0066
"""

import sqlalchemy as sa
from alembic import op

revision = "20261017_0067"
down_revision = "20261017_0066"
branch_labels = None
depends_on = None


def _lower(column: str):
    # The target runtime is PostgreSQL 17; retain SQLite migration/test support.
    collate = ' COLLATE "pg_c_utf8"' if op.get_bind().dialect.name == "postgresql" else ""
    return sa.text(f"lower({column}{collate})")


def upgrade() -> None:
    op.drop_index("ix_public_profiles_published_name", table_name="public_user_profiles")
    op.create_index(
        "ix_public_profiles_published_name",
        "public_user_profiles",
        ["is_published", _lower("display_name"), "id"],
    )
    op.create_index(
        "ix_partner_landings_status_name", "partner_landings", ["status", _lower("title"), "id"]
    )
    # The composite index also covers the previous status-only lookup.
    op.drop_index("ix_partner_landings_status", table_name="partner_landings")


def downgrade() -> None:
    op.create_index("ix_partner_landings_status", "partner_landings", ["status"])
    op.drop_index("ix_partner_landings_status_name", table_name="partner_landings")
    op.drop_index("ix_public_profiles_published_name", table_name="public_user_profiles")
    op.create_index(
        "ix_public_profiles_published_name",
        "public_user_profiles",
        ["is_published", sa.text("lower(display_name)"), "id"],
    )
