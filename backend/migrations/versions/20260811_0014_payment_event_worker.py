"""Harden payment event worker lifecycle invariants.

Revision ID: 20260811_0014
Revises: 20260811_0013
Create Date: 2026-08-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260811_0014"
down_revision: str | Sequence[str] | None = "20260811_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        op.f("ck_payment_events_payment_event_lock_consistent"),
        "payment_events",
        "(status = 'processing' AND locked_at IS NOT NULL AND locked_by IS NOT NULL) OR "
        "(status <> 'processing' AND locked_at IS NULL AND locked_by IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_payment_events_payment_event_processed_at_consistent"),
        "payment_events",
        "(status = 'processed' AND processed_at IS NOT NULL) OR "
        "(status <> 'processed' AND processed_at IS NULL)",
    )
    op.create_index(
        "ix_payment_events_dispatch",
        "payment_events",
        ["status", "available_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_events_dispatch", table_name="payment_events")
    op.drop_constraint(
        op.f("ck_payment_events_payment_event_processed_at_consistent"),
        "payment_events",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_payment_events_payment_event_lock_consistent"),
        "payment_events",
        type_="check",
    )
