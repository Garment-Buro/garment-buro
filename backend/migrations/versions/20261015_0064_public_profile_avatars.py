"""Private, revocable attachments for public user profiles.

Revision ID: 20261015_0064
Revises: 20261015_0063
"""

import sqlalchemy as sa
from alembic import op

revision = "20261015_0064"
down_revision = "20261015_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("public_user_profiles", sa.Column("avatar_media_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_public_user_profiles_avatar_media_id_media_objects"),
        "public_user_profiles",
        "media_objects",
        ["avatar_media_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_public_user_profiles_avatar_media_id", "public_user_profiles", ["avatar_media_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_public_user_profiles_avatar_media_id", table_name="public_user_profiles")
    op.drop_constraint(
        op.f("fk_public_user_profiles_avatar_media_id_media_objects"),
        "public_user_profiles",
        type_="foreignkey",
    )
    op.drop_column("public_user_profiles", "avatar_media_id")
