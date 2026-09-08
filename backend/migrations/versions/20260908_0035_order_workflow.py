"""Persistent moderated order saga and recoverable work queue (no legacy backfill)."""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0035"
down_revision = "20260908_0034"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade():
    op.create_table(
        "order_workflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "payment_attempt_id",
            sa.Integer(),
            sa.ForeignKey("payment_attempts.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True)),
        sa.Column("decision", sa.String(16)),
        sa.Column("decision_key", sa.String(64), unique=True),
        sa.Column(
            "decision_actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")
        ),
        sa.Column("decision_note", sa.Text()),
        sa.Column("attention_code", sa.String(64)),
        sa.Column("cdek_status", sa.String(64)),
        sa.Column("cdek_status_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("version > 0", name="workflow_version_positive"),
        sa.CheckConstraint(
            "(decision IS NULL AND decision_key IS NULL AND decision_actor_id IS NULL AND decision_note IS NULL) OR (decision IS NOT NULL AND decision IN ('approve','reject') AND decision_key IS NOT NULL AND decision_actor_id IS NOT NULL AND decision_note IS NOT NULL)",
            name="workflow_decision_complete",
        ),
        sa.CheckConstraint(
            "state IN ('awaiting_payment','moderation','capture_pending','cancel_pending','production','shipped','completed','cancelled','attention')",
            name="workflow_state_valid",
        ),
    )
    op.create_index("ix_order_workflows_state", "order_workflows", ["state"])
    op.create_table(
        "order_workflow_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("order_workflows.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        *timestamps(),
        sa.UniqueConstraint("workflow_id", "version"),
    )
    op.create_table(
        "order_workflow_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("order_workflows.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column(
            "payment_attempt_id",
            sa.Integer(),
            sa.ForeignKey("payment_attempts.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "shipment_id", sa.Integer(), sa.ForeignKey("cdek_shipments.id", ondelete="RESTRICT")
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("last_error_code", sa.String(64)),
        *timestamps(),
        sa.UniqueConstraint("workflow_id", "kind", "target_id"),
        sa.CheckConstraint(
            "kind IN ('create_payment','decision','track_delivery')", name="workflow_job_kind"
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','completed','dead')", name="workflow_job_status"
        ),
        sa.CheckConstraint("failures >= 0 AND generation >= 0", name="workflow_job_counts"),
        sa.CheckConstraint(
            "(kind IN ('create_payment','decision') AND payment_attempt_id = target_id AND payment_attempt_id IS NOT NULL AND shipment_id IS NULL) OR (kind = 'track_delivery' AND shipment_id = target_id AND shipment_id IS NOT NULL AND payment_attempt_id IS NULL)",
            name="workflow_job_target",
        ),
        sa.CheckConstraint(
            "(status = 'processing' AND lease_until IS NOT NULL AND lease_token IS NOT NULL) OR (status <> 'processing' AND lease_until IS NULL AND lease_token IS NULL)",
            name="workflow_job_lease",
        ),
    )
    op.create_index("ix_workflow_job_due", "order_workflow_jobs", ["status", "available_at"])


def downgrade():
    op.drop_table("order_workflow_jobs")
    op.drop_table("order_workflow_events")
    op.drop_table("order_workflows")
