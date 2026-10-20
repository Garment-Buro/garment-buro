"""Index bounded partner directory and payout continuation.

Revision ID: 20261018_0071
Revises: 20261018_0070
"""

from alembic import op

revision = "20261018_0071"
down_revision = "20261018_0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_partner_profiles_status_id", "partner_profiles", ["status", "id"])
    op.create_index(
        "ix_partner_payouts_owner_recent",
        "partner_payout_requests",
        ["partner_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_partner_payouts_owner_recent", table_name="partner_payout_requests")
    op.drop_index("ix_partner_profiles_status_id", table_name="partner_profiles")
