"""Persistent CDEK pickup directory and cross-process refresh lease."""

import sqlalchemy as sa
from alembic import op

revision = "20260905_0032"
down_revision = "20260904_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_pickup_points",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "delivery_directory_state",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("retry_at", sa.DateTime(timezone=True)),
    )
    op.execute("INSERT INTO delivery_directory_state (key) VALUES ('cdek-ru')")


def downgrade() -> None:
    op.drop_table("delivery_pickup_points")
    op.drop_table("delivery_directory_state")
