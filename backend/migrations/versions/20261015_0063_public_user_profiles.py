"""Separate opt-in public user profiles from private identity fields.

Revision ID: 20261015_0063
Revises: 20261015_0062
"""

import sqlalchemy as sa
from alembic import op

revision = "20261015_0063"
down_revision = "20261015_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_user_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("bio", sa.Text(), server_default="", nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_public_user_profiles")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_public_user_profiles_user_id_users"),
        ),
        sa.UniqueConstraint("user_id", name=op.f("uq_public_user_profiles_user_id")),
        sa.UniqueConstraint("slug", name=op.f("uq_public_user_profiles_slug")),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_public_user_profiles_public_profile_version_positive")
        ),
        sa.CheckConstraint(
            "length(slug) BETWEEN 3 AND 64 AND slug = lower(slug)",
            name=op.f("ck_public_user_profiles_public_profile_slug_valid"),
        ),
        sa.CheckConstraint(
            "length(display_name) BETWEEN 1 AND 120",
            name=op.f("ck_public_user_profiles_public_profile_name_valid"),
        ),
        sa.CheckConstraint(
            "length(bio) <= 2000", name=op.f("ck_public_user_profiles_public_profile_bio_bounded")
        ),
    )
    op.create_index(
        "ix_public_profiles_published_recent", "public_user_profiles", ["is_published", "id"]
    )
    op.create_index(
        "ix_public_profiles_published_name",
        "public_user_profiles",
        ["is_published", sa.text("lower(display_name)"), "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_public_profiles_published_name", table_name="public_user_profiles")
    op.drop_index("ix_public_profiles_published_recent", table_name="public_user_profiles")
    op.drop_table("public_user_profiles")
