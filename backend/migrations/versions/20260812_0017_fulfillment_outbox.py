"""Add durable post-payment fulfillment outbox.

Revision ID: 20260812_0017
Revises: 20260811_0016
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0017"
down_revision: str | Sequence[str] | None = "20260811_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fulfillment_jobs",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("source_payment_attempt_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("attempts_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_reference", sa.String(length=255), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("ck_fulfillment_jobs_fulfillment_job_attempts_valid"),
        ),
        sa.CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 20",
            name=op.f("ck_fulfillment_jobs_fulfillment_job_max_attempts_valid"),
        ),
        sa.CheckConstraint(
            "kind IN ('customer_payment_email', 'cdek_order_create', 'crm_order_project')",
            name=op.f("ck_fulfillment_jobs_fulfillment_job_kind_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'retry', 'completed', 'dead')",
            name=op.f("ck_fulfillment_jobs_fulfillment_job_status_valid"),
        ),
        sa.CheckConstraint(
            "(status = 'processing' AND locked_at IS NOT NULL AND locked_by IS NOT NULL) OR "
            "(status <> 'processing' AND locked_at IS NULL AND locked_by IS NULL)",
            name=op.f("ck_fulfillment_jobs_fulfillment_job_lock_consistent"),
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name=op.f("ck_fulfillment_jobs_fulfillment_job_completed_at_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_fulfillment_jobs_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_payment_attempt_id"],
            ["payment_attempts.id"],
            name=op.f("fk_fulfillment_jobs_source_payment_attempt_id_payment_attempts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fulfillment_jobs")),
        sa.UniqueConstraint(
            "order_id",
            "kind",
            name="uq_fulfillment_job_order_kind",
        ),
    )
    op.create_index(
        "ix_fulfillment_jobs_dispatch",
        "fulfillment_jobs",
        ["status", "available_at"],
    )
    op.create_index(
        op.f("ix_fulfillment_jobs_available_at"),
        "fulfillment_jobs",
        ["available_at"],
    )
    op.create_index(
        op.f("ix_fulfillment_jobs_kind"),
        "fulfillment_jobs",
        ["kind"],
    )
    op.create_index(
        op.f("ix_fulfillment_jobs_locked_at"),
        "fulfillment_jobs",
        ["locked_at"],
    )
    op.create_index(
        op.f("ix_fulfillment_jobs_order_id"),
        "fulfillment_jobs",
        ["order_id"],
    )
    op.create_index(
        op.f("ix_fulfillment_jobs_source_payment_attempt_id"),
        "fulfillment_jobs",
        ["source_payment_attempt_id"],
    )
    op.create_index(
        op.f("ix_fulfillment_jobs_status"),
        "fulfillment_jobs",
        ["status"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        jobs = op.get_bind().execute(sa.text("SELECT count(*) FROM fulfillment_jobs"))
        if jobs.scalar_one():
            raise RuntimeError("Cannot downgrade fulfillment outbox while jobs exist")
    op.drop_index(op.f("ix_fulfillment_jobs_status"), table_name="fulfillment_jobs")
    op.drop_index(
        op.f("ix_fulfillment_jobs_source_payment_attempt_id"),
        table_name="fulfillment_jobs",
    )
    op.drop_index(op.f("ix_fulfillment_jobs_order_id"), table_name="fulfillment_jobs")
    op.drop_index(op.f("ix_fulfillment_jobs_locked_at"), table_name="fulfillment_jobs")
    op.drop_index(op.f("ix_fulfillment_jobs_kind"), table_name="fulfillment_jobs")
    op.drop_index(op.f("ix_fulfillment_jobs_available_at"), table_name="fulfillment_jobs")
    op.drop_index("ix_fulfillment_jobs_dispatch", table_name="fulfillment_jobs")
    op.drop_table("fulfillment_jobs")
