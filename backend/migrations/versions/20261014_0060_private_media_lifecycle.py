"""Index bounded cleanup of private project uploads.

Revision ID: 20261014_0060
Revises: 20261013_0059
"""

import sqlalchemy as sa
from alembic import op

revision = "20261014_0060"
down_revision = "20261013_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_media_objects_private_lifecycle",
        "media_objects",
        ["bucket_name", "status", "updated_at", "id"],
        postgresql_where=sa.text("is_public IS FALSE"),
        sqlite_where=sa.text("is_public = 0"),
    )


def downgrade() -> None:
    op.drop_index("ix_media_objects_private_lifecycle", table_name="media_objects")
