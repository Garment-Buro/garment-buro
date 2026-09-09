"""Explicit demo orders without fabricated payment or fulfillment evidence."""

import sqlalchemy as sa
from alembic import context, op

revision = "20260909_0038"
down_revision = "20260909_0037"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "orders", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    with op.batch_alter_table("crm_order_projects") as batch:
        batch.add_column(
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.alter_column("source_fulfillment_job_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("source_payment_attempt_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column(
            "payment_succeeded_at_snapshot", existing_type=sa.DateTime(timezone=True), nullable=True
        )
        batch.create_check_constraint(
            "crm_project_payment_evidence_or_demo",
            "(is_demo AND source_fulfillment_job_id IS NULL AND source_payment_attempt_id IS NULL AND payment_succeeded_at_snapshot IS NULL) "
            "OR (NOT is_demo AND source_fulfillment_job_id IS NOT NULL AND source_payment_attempt_id IS NOT NULL AND payment_succeeded_at_snapshot IS NOT NULL)",
        )
    op.create_table(
        "production_demo_employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("station", sa.String(24), nullable=False, unique=True),
    )


def downgrade():
    if not context.is_offline_mode() and op.get_bind().scalar(
        sa.text("SELECT count(*) FROM orders WHERE is_demo")
    ):
        raise RuntimeError("Archive demo data explicitly before a schema downgrade")
    op.drop_table("production_demo_employees")
    with op.batch_alter_table("crm_order_projects") as batch:
        batch.drop_constraint("crm_project_payment_evidence_or_demo", type_="check")
        batch.drop_column("is_demo")
        batch.alter_column("source_fulfillment_job_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("source_payment_attempt_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column(
            "payment_succeeded_at_snapshot",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
    op.drop_column("orders", "is_demo")
