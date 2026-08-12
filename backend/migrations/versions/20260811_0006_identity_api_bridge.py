"""Add guarded identity API ownership bridge.

Revision ID: 20260811_0006
Revises: 20260811_0005
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0006"
down_revision: str | Sequence[str] | None = "20260811_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_outbox",
        sa.Column("discard_after", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_notification_outbox_discard_after"),
        "notification_outbox",
        ["discard_after"],
    )

    op.drop_constraint(
        op.f("ck_users_user_identifier_present"),
        "users",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_users_user_identifier_present"),
        "users",
        "status = 'deleted' OR email_normalized IS NOT NULL OR telegram_id IS NOT NULL",
    )

    op.create_table(
        "legacy_order_claims",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("legacy_order_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("identifier_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(identifier_digest) = 64",
            name=op.f("ck_legacy_order_claims_legacy_order_claim_identifier_digest_length"),
        ),
        sa.CheckConstraint(
            "legacy_order_id > 0",
            name=op.f("ck_legacy_order_claims_legacy_order_claim_order_id_positive"),
        ),
        sa.CheckConstraint(
            "source IN ('verified_email')",
            name=op.f("ck_legacy_order_claims_legacy_order_claim_source_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_legacy_order_claims_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legacy_order_claims")),
        sa.UniqueConstraint(
            "legacy_order_id",
            name="uq_legacy_order_claim_legacy_order_id",
        ),
    )
    op.create_index(
        op.f("ix_legacy_order_claims_user_id"),
        "legacy_order_claims",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_legacy_order_claims_user_id"),
        table_name="legacy_order_claims",
    )
    op.drop_table("legacy_order_claims")

    op.drop_constraint(
        op.f("ck_users_user_identifier_present"),
        "users",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_users_user_identifier_present"),
        "users",
        "email_normalized IS NOT NULL OR telegram_id IS NOT NULL",
    )

    op.drop_index(
        op.f("ix_notification_outbox_discard_after"),
        table_name="notification_outbox",
    )
    op.drop_column("notification_outbox", "discard_after")
