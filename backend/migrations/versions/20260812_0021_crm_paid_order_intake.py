"""Add the PII-free CRM paid-order production intake.

Revision ID: 20260812_0021
Revises: 20260812_0020
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0021"
down_revision: str | Sequence[str] | None = "20260812_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_order_projects",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("source_fulfillment_job_id", sa.Integer(), nullable=False),
        sa.Column("source_payment_attempt_id", sa.Integer(), nullable=False),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("order_version_snapshot", sa.Integer(), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
        sa.Column("units_count", sa.Integer(), nullable=False),
        sa.Column("total_price_snapshot", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payment_succeeded_at_snapshot", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
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
            "currency = 'RUB'",
            name=op.f("ck_crm_order_projects_crm_order_project_currency_rub"),
        ),
        sa.CheckConstraint(
            "items_count > 0",
            name=op.f("ck_crm_order_projects_crm_order_project_items_count_positive"),
        ),
        sa.CheckConstraint(
            "(status = 'in_progress' AND started_at IS NOT NULL AND closed_at IS NULL) OR "
            "(status = 'completed' AND started_at IS NOT NULL AND closed_at IS NOT NULL) OR "
            "(status = 'cancelled' AND closed_at IS NOT NULL) OR "
            "(status IN ('queued', 'on_hold') AND closed_at IS NULL)",
            name=op.f("ck_crm_order_projects_crm_order_project_lifecycle_timestamps_consistent"),
        ),
        sa.CheckConstraint(
            "order_version_snapshot > 0",
            name=op.f("ck_crm_order_projects_crm_order_project_order_version_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'in_progress', 'on_hold', 'completed', 'cancelled')",
            name=op.f("ck_crm_order_projects_crm_order_project_status_valid"),
        ),
        sa.CheckConstraint(
            "total_price_snapshot >= 0",
            name=op.f("ck_crm_order_projects_crm_order_project_total_nonnegative"),
        ),
        sa.CheckConstraint(
            "units_count > 0",
            name=op.f("ck_crm_order_projects_crm_order_project_units_count_positive"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_order_projects_crm_order_project_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"],
            ["users.id"],
            name=op.f("fk_crm_order_projects_assigned_to_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_crm_order_projects_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_fulfillment_job_id"],
            ["fulfillment_jobs.id"],
            name=op.f("fk_crm_order_projects_source_fulfillment_job_id_fulfillment_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_payment_attempt_id"],
            ["payment_attempts.id"],
            name=op.f("fk_crm_order_projects_source_payment_attempt_id_payment_attempts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_order_projects")),
        sa.UniqueConstraint("order_id", name=op.f("uq_crm_order_projects_order_id")),
        sa.UniqueConstraint(
            "source_fulfillment_job_id",
            name=op.f("uq_crm_order_projects_source_fulfillment_job_id"),
        ),
    )
    for column in (
        "assigned_to_user_id",
        "order_id",
        "source_fulfillment_job_id",
        "source_payment_attempt_id",
        "status",
    ):
        op.create_index(op.f(f"ix_crm_order_projects_{column}"), "crm_order_projects", [column])
    op.create_index(
        "ix_crm_order_projects_status_created",
        "crm_order_projects",
        ["status", "created_at"],
    )

    op.create_table(
        "crm_production_units",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("product_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("variant_id_snapshot", sa.Integer(), nullable=True),
        sa.Column("unit_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="queued", nullable=False),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
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
            "unit_number > 0",
            name=op.f("ck_crm_production_units_crm_production_unit_number_positive"),
        ),
        sa.CheckConstraint(
            "product_id_snapshot > 0",
            name=op.f("ck_crm_production_units_crm_production_unit_product_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'in_progress', 'quality_control', 'completed', 'cancelled')",
            name=op.f("ck_crm_production_units_crm_production_unit_status_valid"),
        ),
        sa.CheckConstraint(
            "variant_id_snapshot IS NULL OR variant_id_snapshot > 0",
            name=op.f("ck_crm_production_units_crm_production_unit_variant_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"],
            ["users.id"],
            name=op.f("fk_crm_production_units_assigned_to_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("fk_crm_production_units_order_item_id_order_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["crm_order_projects.id"],
            name=op.f("fk_crm_production_units_project_id_crm_order_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_production_units")),
        sa.UniqueConstraint(
            "project_id",
            "order_item_id",
            "unit_number",
            name="uq_crm_production_unit_source",
        ),
    )
    for column in (
        "assigned_to_user_id",
        "order_item_id",
        "product_id_snapshot",
        "project_id",
        "status",
        "variant_id_snapshot",
    ):
        op.create_index(
            op.f(f"ix_crm_production_units_{column}"),
            "crm_production_units",
            [column],
        )
    op.create_index(
        "ix_crm_production_units_status_created",
        "crm_production_units",
        ["status", "created_at"],
    )

    op.create_table(
        "crm_project_events",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('queued', 'in_progress', 'on_hold', 'completed', 'cancelled')",
            name=op.f("ck_crm_project_events_crm_project_event_from_status_valid"),
        ),
        sa.CheckConstraint(
            "to_status IN ('queued', 'in_progress', 'on_hold', 'completed', 'cancelled')",
            name=op.f("ck_crm_project_events_crm_project_event_to_status_valid"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_project_events_crm_project_event_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_crm_project_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["crm_order_projects.id"],
            name=op.f("fk_crm_project_events_project_id_crm_order_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_project_events")),
        sa.UniqueConstraint("event_key", name="uq_crm_project_event_key"),
        sa.UniqueConstraint("project_id", "version", name="uq_crm_project_event_version"),
    )
    for column in (
        "actor_user_id",
        "occurred_at",
        "project_id",
        "to_status",
    ):
        op.create_index(
            op.f(f"ix_crm_project_events_{column}"),
            "crm_project_events",
            [column],
        )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        projects = bind.execute(sa.text("SELECT count(*) FROM crm_order_projects")).scalar_one()
        if projects:
            raise RuntimeError("Cannot downgrade CRM intake while production projects exist")

    for index_name in (
        "ix_crm_project_events_to_status",
        "ix_crm_project_events_project_id",
        "ix_crm_project_events_occurred_at",
        "ix_crm_project_events_actor_user_id",
    ):
        op.drop_index(index_name, table_name="crm_project_events")
    op.drop_table("crm_project_events")
    for index_name in (
        "ix_crm_production_units_status_created",
        "ix_crm_production_units_variant_id_snapshot",
        "ix_crm_production_units_status",
        "ix_crm_production_units_project_id",
        "ix_crm_production_units_product_id_snapshot",
        "ix_crm_production_units_order_item_id",
        "ix_crm_production_units_assigned_to_user_id",
    ):
        op.drop_index(index_name, table_name="crm_production_units")
    op.drop_table("crm_production_units")
    for index_name in (
        "ix_crm_order_projects_status_created",
        "ix_crm_order_projects_status",
        "ix_crm_order_projects_source_payment_attempt_id",
        "ix_crm_order_projects_source_fulfillment_job_id",
        "ix_crm_order_projects_order_id",
        "ix_crm_order_projects_assigned_to_user_id",
    ):
        op.drop_index(index_name, table_name="crm_order_projects")
    op.drop_table("crm_order_projects")
