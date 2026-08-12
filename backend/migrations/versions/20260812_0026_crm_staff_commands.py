"""Add idempotent CRM staff commands and assignment audit.

Revision ID: 20260812_0026
Revises: 20260812_0025
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0026"
down_revision: str | Sequence[str] | None = "20260812_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_assignment_events",
        sa.Column("production_project_id", sa.Integer(), nullable=True),
        sa.Column("production_unit_id", sa.Integer(), nullable=True),
        sa.Column("event_key", sa.String(128), nullable=False),
        sa.Column("entity_version", sa.Integer(), nullable=False),
        sa.Column("from_assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("to_assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(production_project_id IS NOT NULL AND production_unit_id IS NULL) OR "
            "(production_project_id IS NULL AND production_unit_id IS NOT NULL)",
            name=op.f("ck_crm_assignment_events_crm_assignment_exactly_one_target"),
        ),
        sa.CheckConstraint(
            "entity_version > 0",
            name=op.f("ck_crm_assignment_events_crm_assignment_version_positive"),
        ),
        sa.CheckConstraint(
            "(from_assigned_to_user_id IS NULL AND to_assigned_to_user_id IS NOT NULL) OR "
            "(from_assigned_to_user_id IS NOT NULL AND to_assigned_to_user_id IS NULL) OR "
            "(from_assigned_to_user_id IS NOT NULL AND to_assigned_to_user_id IS NOT NULL "
            "AND from_assigned_to_user_id <> to_assigned_to_user_id)",
            name=op.f("ck_crm_assignment_events_crm_assignment_changed"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_crm_assignment_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["from_assigned_to_user_id"],
            ["users.id"],
            name=op.f("fk_crm_assignment_events_from_assigned_to_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["production_project_id"],
            ["crm_order_projects.id"],
            name=op.f("fk_crm_assignment_events_production_project_id_crm_order_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["production_unit_id"],
            ["crm_production_units.id"],
            name=op.f("fk_crm_assignment_events_production_unit_id_crm_production_units"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_assigned_to_user_id"],
            ["users.id"],
            name=op.f("fk_crm_assignment_events_to_assigned_to_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_assignment_events")),
        sa.UniqueConstraint("event_key", name="uq_crm_assignment_event_key"),
        sa.UniqueConstraint(
            "production_project_id",
            "entity_version",
            name="uq_crm_assignment_project_version",
        ),
        sa.UniqueConstraint(
            "production_unit_id",
            "entity_version",
            name="uq_crm_assignment_unit_version",
        ),
    )
    for column in (
        "actor_user_id",
        "from_assigned_to_user_id",
        "occurred_at",
        "production_project_id",
        "production_unit_id",
        "to_assigned_to_user_id",
    ):
        op.create_index(
            op.f(f"ix_crm_assignment_events_{column}"),
            "crm_assignment_events",
            [column],
        )

    op.create_table(
        "crm_staff_commands",
        sa.Column("idempotency_key_sha256", sa.String(64), nullable=False),
        sa.Column("command_sha256", sa.String(64), nullable=False),
        sa.Column("command_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="processing", nullable=False),
        sa.Column("result_version", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "command_type IN ('project.assign', 'project.transition', "
            "'unit.assign', 'unit.transition')",
            name=op.f("ck_crm_staff_commands_crm_staff_command_type_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'completed')",
            name=op.f("ck_crm_staff_commands_crm_staff_command_status_valid"),
        ),
        sa.CheckConstraint(
            "target_id > 0",
            name=op.f("ck_crm_staff_commands_crm_staff_command_target_positive"),
        ),
        sa.CheckConstraint(
            "length(idempotency_key_sha256) = 64 AND length(command_sha256) = 64",
            name=op.f("ck_crm_staff_commands_crm_staff_command_digests_valid"),
        ),
        sa.CheckConstraint(
            "(status = 'processing' AND result_version IS NULL AND completed_at IS NULL) OR "
            "(status = 'completed' AND result_version > 0 AND completed_at IS NOT NULL)",
            name=op.f("ck_crm_staff_commands_crm_staff_command_completion_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_crm_staff_commands_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_staff_commands")),
    )
    for column in ("actor_user_id", "command_type", "status", "target_id"):
        op.create_index(
            op.f(f"ix_crm_staff_commands_{column}"),
            "crm_staff_commands",
            [column],
        )
    op.create_index(
        op.f("ix_crm_staff_commands_idempotency_key_sha256"),
        "crm_staff_commands",
        ["idempotency_key_sha256"],
        unique=True,
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        assignments = connection.execute(
            sa.text("SELECT count(*) FROM crm_assignment_events")
        ).scalar_one()
        commands = connection.execute(
            sa.text("SELECT count(*) FROM crm_staff_commands")
        ).scalar_one()
        if assignments or commands:
            raise RuntimeError("Cannot downgrade CRM staff commands while audit evidence exists")
    for name in (
        "ix_crm_staff_commands_idempotency_key_sha256",
        "ix_crm_staff_commands_target_id",
        "ix_crm_staff_commands_status",
        "ix_crm_staff_commands_command_type",
        "ix_crm_staff_commands_actor_user_id",
    ):
        op.drop_index(name, table_name="crm_staff_commands")
    op.drop_table("crm_staff_commands")
    for name in (
        "ix_crm_assignment_events_to_assigned_to_user_id",
        "ix_crm_assignment_events_production_unit_id",
        "ix_crm_assignment_events_production_project_id",
        "ix_crm_assignment_events_occurred_at",
        "ix_crm_assignment_events_from_assigned_to_user_id",
        "ix_crm_assignment_events_actor_user_id",
    ):
        op.drop_index(name, table_name="crm_assignment_events")
    op.drop_table("crm_assignment_events")
