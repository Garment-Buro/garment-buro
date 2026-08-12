"""Add durable payment reconciliation jobs.

Revision ID: 20260811_0015
Revises: 20260811_0014
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0015"
down_revision: str | Sequence[str] | None = "20260811_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_reconciliation_jobs",
        sa.Column("payment_attempt_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'scheduled'"),
            nullable=False,
        ),
        sa.Column("attempts_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_observation_sha256", sa.String(length=64), nullable=True),
        sa.Column("last_observed_status", sa.String(length=32), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
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
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name=op.f("ck_payment_reconciliation_jobs_payment_reconciliation_attempts_valid"),
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name=op.f(
                "ck_payment_reconciliation_jobs_payment_reconciliation_completed_at_consistent"
            ),
        ),
        sa.CheckConstraint(
            "(status = 'processing' AND locked_at IS NOT NULL AND locked_by IS NOT NULL) OR "
            "(status <> 'processing' AND locked_at IS NULL AND locked_by IS NULL)",
            name=op.f("ck_payment_reconciliation_jobs_payment_reconciliation_lock_consistent"),
        ),
        sa.CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 1000",
            name=op.f("ck_payment_reconciliation_jobs_payment_reconciliation_max_attempts_valid"),
        ),
        sa.CheckConstraint(
            "(last_observation_sha256 IS NULL AND last_observed_status IS NULL) OR "
            "(length(last_observation_sha256) = 64 AND last_observed_status IN "
            "('pending', 'waiting_for_capture', 'succeeded', 'canceled'))",
            name=op.f(
                "ck_payment_reconciliation_jobs_payment_reconciliation_observation_consistent"
            ),
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'processing', 'retry', 'completed', 'dead')",
            name=op.f("ck_payment_reconciliation_jobs_payment_reconciliation_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id"],
            ["payment_attempts.id"],
            name=op.f("fk_payment_reconciliation_jobs_payment_attempt_id_payment_attempts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_reconciliation_jobs")),
        sa.UniqueConstraint(
            "payment_attempt_id",
            name="uq_payment_reconciliation_job_attempt",
        ),
    )
    op.create_index(
        "ix_payment_reconciliation_dispatch",
        "payment_reconciliation_jobs",
        ["status", "available_at"],
    )
    op.create_index(
        op.f("ix_payment_reconciliation_jobs_available_at"),
        "payment_reconciliation_jobs",
        ["available_at"],
    )
    op.create_index(
        op.f("ix_payment_reconciliation_jobs_locked_at"),
        "payment_reconciliation_jobs",
        ["locked_at"],
    )
    op.create_index(
        op.f("ix_payment_reconciliation_jobs_payment_attempt_id"),
        "payment_reconciliation_jobs",
        ["payment_attempt_id"],
    )
    op.create_index(
        op.f("ix_payment_reconciliation_jobs_status"),
        "payment_reconciliation_jobs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_payment_reconciliation_jobs_status"),
        table_name="payment_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_payment_reconciliation_jobs_payment_attempt_id"),
        table_name="payment_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_payment_reconciliation_jobs_locked_at"),
        table_name="payment_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_payment_reconciliation_jobs_available_at"),
        table_name="payment_reconciliation_jobs",
    )
    op.drop_index(
        "ix_payment_reconciliation_dispatch",
        table_name="payment_reconciliation_jobs",
    )
    op.drop_table("payment_reconciliation_jobs")
