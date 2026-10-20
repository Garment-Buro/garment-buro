"""Persist independent buyer and recipient contact snapshots.

Revision ID: 20261014_0061
Revises: 20261014_0060
"""

import sqlalchemy as sa
from alembic import op

revision = "20261014_0061"
down_revision = "20261014_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical contacts cannot be reconstructed reliably. Older rows and
    # older-image inserts retain NULL snapshots; existing columns are untouched.
    op.add_column("orders", sa.Column("buyer_name", sa.String(255), nullable=True))
    op.add_column("orders", sa.Column("buyer_phone", sa.String(64), nullable=True))
    op.add_column("orders", sa.Column("recipient_email", sa.String(320), nullable=True))
    op.create_check_constraint(
        "order_contact_snapshots_complete",
        "orders",
        "(buyer_name IS NULL AND buyer_phone IS NULL AND recipient_email IS NULL) OR "
        "(buyer_name IS NOT NULL AND length(trim(buyer_name)) > 0 "
        "AND buyer_phone IS NOT NULL AND length(trim(buyer_phone)) > 0 "
        "AND recipient_email IS NOT NULL AND length(trim(recipient_email)) > 0)",
    )


def downgrade() -> None:
    op.drop_constraint("order_contact_snapshots_complete", "orders", type_="check")
    op.drop_column("orders", "recipient_email")
    op.drop_column("orders", "buyer_phone")
    op.drop_column("orders", "buyer_name")
