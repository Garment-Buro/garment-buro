"""Persist customer favorites for published community landings.

Revision ID: 20261015_0062
Revises: 20261014_0061
"""

import sqlalchemy as sa
from alembic import op

revision = "20261015_0062"
down_revision = "20261014_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_community_favorites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("landing_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_community_favorites")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_user_community_favorites_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["landing_id"],
            ["partner_landings.id"],
            ondelete="CASCADE",
            name=op.f("fk_user_community_favorites_landing_id_partner_landings"),
        ),
        sa.UniqueConstraint(
            "user_id", "landing_id", name="uq_user_community_favorites_user_landing"
        ),
    )
    op.create_index(
        "ix_user_community_favorites_user_recent", "user_community_favorites", ["user_id", "id"]
    )
    op.create_index(
        op.f("ix_user_community_favorites_landing_id"), "user_community_favorites", ["landing_id"]
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_community_favorites_landing_id"), table_name="user_community_favorites"
    )
    op.drop_index("ix_user_community_favorites_user_recent", table_name="user_community_favorites")
    op.drop_table("user_community_favorites")
