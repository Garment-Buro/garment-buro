"""Bounded keyset lookup for direct and claimed customer orders.

Revision ID: 20261017_0066
Revises: 20261016_0065
"""

from alembic import op

revision = "20261017_0066"
down_revision = "20261016_0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_orders_owner_recent", "orders", ["user_id", "id"])
    op.create_index(
        "ix_legacy_order_claims_owner_recent", "legacy_order_claims", ["user_id", "legacy_order_id"]
    )
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_index("ix_legacy_order_claims_user_id", table_name="legacy_order_claims")


def downgrade() -> None:
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_legacy_order_claims_user_id", "legacy_order_claims", ["user_id"])
    op.drop_index("ix_orders_owner_recent", table_name="orders")
    op.drop_index("ix_legacy_order_claims_owner_recent", table_name="legacy_order_claims")
