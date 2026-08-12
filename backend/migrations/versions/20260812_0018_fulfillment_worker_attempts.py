"""Add fulfillment worker attempt history.

Revision ID: 20260812_0018
Revises: 20260812_0017
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0018"
down_revision: str | Sequence[str] | None = "20260812_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fulfillment_job_attempts",
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("result_reference", sa.String(length=255), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "attempt_number > 0",
            name=op.f("ck_fulfillment_job_attempts_fulfillment_job_attempt_number_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'retry', 'completed', 'dead', 'abandoned')",
            name=op.f("ck_fulfillment_job_attempts_fulfillment_job_attempt_status_valid"),
        ),
        sa.CheckConstraint(
            "(status = 'processing' AND finished_at IS NULL) OR "
            "(status <> 'processing' AND finished_at IS NOT NULL)",
            name=op.f("ck_fulfillment_job_attempts_fulfillment_job_attempt_finished_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["fulfillment_jobs.id"],
            name=op.f("fk_fulfillment_job_attempts_job_id_fulfillment_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fulfillment_job_attempts")),
        sa.UniqueConstraint(
            "job_id",
            "attempt_number",
            name="uq_fulfillment_job_attempt_number",
        ),
    )
    op.create_index(
        op.f("ix_fulfillment_job_attempts_job_id"),
        "fulfillment_job_attempts",
        ["job_id"],
    )
    op.create_index(
        op.f("ix_fulfillment_job_attempts_status"),
        "fulfillment_job_attempts",
        ["status"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        attempts = op.get_bind().execute(sa.text("SELECT count(*) FROM fulfillment_job_attempts"))
        if attempts.scalar_one():
            raise RuntimeError("Cannot downgrade fulfillment worker history while attempts exist")
    op.drop_index(
        op.f("ix_fulfillment_job_attempts_status"),
        table_name="fulfillment_job_attempts",
    )
    op.drop_index(
        op.f("ix_fulfillment_job_attempts_job_id"),
        table_name="fulfillment_job_attempts",
    )
    op.drop_table("fulfillment_job_attempts")
