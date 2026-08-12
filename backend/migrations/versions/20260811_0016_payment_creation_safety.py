"""Add durable payment creation safety evidence.

Revision ID: 20260811_0016
Revises: 20260811_0015
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260811_0016"
down_revision: str | Sequence[str] | None = "20260811_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payment_attempts",
        sa.Column("provider_request_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "payment_attempts",
        sa.Column("creation_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "payment_attempts",
        sa.Column("creation_last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "payment_attempts",
        sa.Column(
            "creation_attempts_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.drop_constraint(
        op.f("ck_payment_attempts_payment_attempt_status_valid"),
        "payment_attempts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_payment_attempts_payment_attempt_provider_id_present"),
        "payment_attempts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_payment_attempts_payment_attempt_resolution_after_creation"),
        "payment_attempts",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_payment_attempts_payment_attempt_status_valid"),
        "payment_attempts",
        "status IN ('prepared', 'unknown', 'failed', 'pending', "
        "'waiting_for_capture', 'succeeded', 'canceled')",
    )
    op.create_check_constraint(
        op.f("ck_payment_attempts_payment_attempt_provider_id_present"),
        "payment_attempts",
        "provider_payment_id IS NOT NULL OR status IN ('prepared', 'unknown', 'failed')",
    )
    op.create_check_constraint(
        op.f("ck_payment_attempts_payment_attempt_resolution_after_creation"),
        "payment_attempts",
        "(status IN ('failed', 'succeeded', 'canceled') AND resolved_at IS NOT NULL "
        "AND resolved_at >= created_at) OR "
        "(status NOT IN ('failed', 'succeeded', 'canceled') AND resolved_at IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_payment_attempts_payment_attempt_creation_consistent"),
        "payment_attempts",
        "(provider_request_sha256 IS NULL AND creation_started_at IS NULL "
        "AND creation_last_attempt_at IS NULL AND creation_attempts_count = 0) OR "
        "(length(provider_request_sha256) = 64 AND creation_started_at IS NOT NULL "
        "AND creation_last_attempt_at IS NOT NULL AND creation_attempts_count > 0 "
        "AND creation_last_attempt_at >= creation_started_at)",
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        failed_attempts = op.get_bind().execute(
            sa.text("SELECT count(*) FROM payment_attempts WHERE status = 'failed'")
        )
        if failed_attempts.scalar_one():
            raise RuntimeError(
                "Cannot downgrade payment creation safety while failed attempts exist"
            )
    op.drop_constraint(
        op.f("ck_payment_attempts_payment_attempt_creation_consistent"),
        "payment_attempts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_payment_attempts_payment_attempt_resolution_after_creation"),
        "payment_attempts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_payment_attempts_payment_attempt_provider_id_present"),
        "payment_attempts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_payment_attempts_payment_attempt_status_valid"),
        "payment_attempts",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_payment_attempts_payment_attempt_status_valid"),
        "payment_attempts",
        "status IN ('prepared', 'unknown', 'pending', 'waiting_for_capture', "
        "'succeeded', 'canceled')",
    )
    op.create_check_constraint(
        op.f("ck_payment_attempts_payment_attempt_provider_id_present"),
        "payment_attempts",
        "provider_payment_id IS NOT NULL OR status IN ('prepared', 'unknown')",
    )
    op.create_check_constraint(
        op.f("ck_payment_attempts_payment_attempt_resolution_after_creation"),
        "payment_attempts",
        "(status IN ('succeeded', 'canceled') AND resolved_at IS NOT NULL "
        "AND resolved_at >= created_at) OR "
        "(status NOT IN ('succeeded', 'canceled') AND resolved_at IS NULL)",
    )
    op.drop_column("payment_attempts", "creation_attempts_count")
    op.drop_column("payment_attempts", "creation_last_attempt_at")
    op.drop_column("payment_attempts", "creation_started_at")
    op.drop_column("payment_attempts", "provider_request_sha256")
