"""Persist partner bank drafts, encrypted instructions and reconciliation events.

Revision ID: 20260908_0033
Revises: 20260905_0032
"""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0033"
down_revision = "20260905_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "partner_bank_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payout_id",
            sa.Integer(),
            sa.ForeignKey("partner_payout_requests.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(20), nullable=False, server_default="tochka"),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("request_id", sa.String(128), unique=True),
        sa.Column("signing_url", sa.Text()),
        sa.Column("provider_status", sa.String(32)),
        sa.Column("command_sha256", sa.String(64), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("tag", sa.String(64), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("last_error", sa.String(64)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("provider = 'tochka'", name="bank_payment_provider_valid"),
        sa.CheckConstraint(
            "environment IN ('sandbox', 'production')", name="bank_payment_environment_valid"
        ),
        sa.CheckConstraint(
            "state IN ('submitting', 'unknown', 'awaiting_signature', 'processing', 'paid', 'rejected', 'canceled')",
            name="bank_payment_state_valid",
        ),
    )
    op.create_index("ix_partner_bank_payments_state", "partner_bank_payments", ["state"])
    op.create_table(
        "partner_bank_payment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("partner_bank_payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("provider_status", sa.String(32)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_partner_bank_payment_events_payment_id", "partner_bank_payment_events", ["payment_id"]
    )


def downgrade() -> None:
    op.drop_table("partner_bank_payment_events")
    op.drop_table("partner_bank_payments")
