"""Persist customer favorites linked to real catalog products.

Revision ID: 20261013_0057
Revises: 20261013_0056
"""

import sqlalchemy as sa
from alembic import op

revision = "20261013_0057"
down_revision = "20261013_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_favorites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_favorites")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_user_favorites_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
            name=op.f("fk_user_favorites_product_id_products"),
        ),
        sa.UniqueConstraint("user_id", "product_id", name="uq_user_favorites_user_product"),
    )
    op.create_index("ix_user_favorites_user_recent", "user_favorites", ["user_id", "id"])
    op.create_index(op.f("ix_user_favorites_product_id"), "user_favorites", ["product_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_user_favorites_product_id"), table_name="user_favorites")
    op.drop_index("ix_user_favorites_user_recent", table_name="user_favorites")
    op.drop_table("user_favorites")
