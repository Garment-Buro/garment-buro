"""Merge the deployed auth history with the release foundation.

Revision ID: 20261020_0081
Revises: 20261019_0080, 20261012_0056
Create Date: 2026-10-20

Both existing branches remain byte-for-byte intact. The password user FK is
already covered by its unique constraint, so its duplicate index is removed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261020_0081"
down_revision: str | Sequence[str] | None = ("20261019_0080", "20261012_0056")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_password_credentials_user_id", table_name="password_credentials")


def downgrade() -> None:
    op.create_index("ix_password_credentials_user_id", "password_credentials", ["user_id"])
