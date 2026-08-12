"""Pin production plans and add versioned unit workflow events.

Revision ID: 20260812_0023
Revises: 20260812_0022
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0023"
down_revision: str | Sequence[str] | None = "20260812_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "crm_production_units",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "crm_production_units",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "crm_production_units",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    if not context.is_offline_mode():
        nonqueued = (
            op.get_bind()
            .execute(sa.text("SELECT count(*) FROM crm_production_units WHERE status <> 'queued'"))
            .scalar_one()
        )
        if nonqueued:
            raise RuntimeError(
                "CRM production workflow migration requires all existing units to be queued"
            )
    op.create_check_constraint(
        op.f("ck_crm_production_units_crm_production_unit_version_positive"),
        "crm_production_units",
        "version > 0",
    )
    op.create_check_constraint(
        op.f("ck_crm_production_units_crm_production_unit_lifecycle_timestamps_consistent"),
        "crm_production_units",
        "(status = 'queued' AND started_at IS NULL AND closed_at IS NULL) OR "
        "(status IN ('in_progress', 'quality_control') AND started_at IS NOT NULL "
        "AND closed_at IS NULL) OR "
        "(status = 'completed' AND started_at IS NOT NULL AND closed_at IS NOT NULL) OR "
        "(status = 'cancelled' AND closed_at IS NOT NULL)",
    )

    op.create_table(
        "crm_production_plan_revisions",
        sa.Column("production_unit_id", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("based_on_plan_revision_id", sa.Integer(), nullable=True),
        sa.Column("garment_model_id", sa.Integer(), nullable=False),
        sa.Column("garment_size_id", sa.Integer(), nullable=True),
        sa.Column("tech_card_revision_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("planned_by_user_id", sa.Integer(), nullable=True),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'superseded')",
            name=op.f("ck_crm_production_plan_revisions_crm_production_plan_status_valid"),
        ),
        sa.CheckConstraint(
            "revision_number > 0",
            name=op.f("ck_crm_production_plan_revisions_crm_production_plan_revision_positive"),
        ),
        sa.CheckConstraint(
            "length(evidence_sha256) = 64",
            name=op.f(
                "ck_crm_production_plan_revisions_crm_production_plan_evidence_digest_length"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["production_unit_id", "based_on_plan_revision_id"],
            [
                "crm_production_plan_revisions.production_unit_id",
                "crm_production_plan_revisions.id",
            ],
            name="fk_crm_production_plan_same_unit_base",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["garment_model_id"],
            ["crm_garment_models.id"],
            name=op.f("fk_crm_production_plan_revisions_garment_model_id_crm_garment_models"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["garment_size_id"],
            ["crm_garment_sizes.id"],
            name=op.f("fk_crm_production_plan_revisions_garment_size_id_crm_garment_sizes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["planned_by_user_id"],
            ["users.id"],
            name=op.f("fk_crm_production_plan_revisions_planned_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["production_unit_id"],
            ["crm_production_units.id"],
            name=op.f("fk_crm_production_plan_revisions_production_unit_id_crm_production_units"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tech_card_revision_id"],
            ["crm_tech_card_revisions.id"],
            name=op.f(
                "fk_crm_production_plan_revisions_tech_card_revision_id_crm_tech_card_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_production_plan_revisions")),
        sa.UniqueConstraint(
            "production_unit_id",
            "id",
            name="uq_crm_production_plan_unit_identity",
        ),
        sa.UniqueConstraint(
            "production_unit_id",
            "revision_number",
            name="uq_crm_production_plan_revision_number",
        ),
    )
    for column in (
        "based_on_plan_revision_id",
        "garment_model_id",
        "garment_size_id",
        "planned_at",
        "planned_by_user_id",
        "production_unit_id",
        "status",
        "tech_card_revision_id",
    ):
        op.create_index(
            op.f(f"ix_crm_production_plan_revisions_{column}"),
            "crm_production_plan_revisions",
            [column],
        )
    op.create_index(
        "uq_crm_production_plan_active",
        "crm_production_plan_revisions",
        ["production_unit_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "crm_production_unit_events",
        sa.Column("production_unit_id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("production_plan_revision_id", sa.Integer(), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_production_unit_events_crm_production_unit_event_version_positive"),
        ),
        sa.CheckConstraint(
            "event_type IN ('initialized', 'planned', 'status_changed')",
            name=op.f("ck_crm_production_unit_events_crm_production_unit_event_type_valid"),
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('queued', 'in_progress', 'quality_control', 'completed', 'cancelled')",
            name=op.f("ck_crm_production_unit_events_crm_production_unit_event_from_status_valid"),
        ),
        sa.CheckConstraint(
            "to_status IN ('queued', 'in_progress', 'quality_control', 'completed', 'cancelled')",
            name=op.f("ck_crm_production_unit_events_crm_production_unit_event_to_status_valid"),
        ),
        sa.CheckConstraint(
            "(event_type = 'initialized' AND from_status IS NULL "
            "AND production_plan_revision_id IS NULL) OR "
            "(event_type = 'planned' AND from_status = to_status "
            "AND production_plan_revision_id IS NOT NULL) OR "
            "(event_type = 'status_changed' AND from_status IS NOT NULL "
            "AND from_status <> to_status)",
            name=op.f("ck_crm_production_unit_events_crm_production_unit_event_shape_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_crm_production_unit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["production_plan_revision_id"],
            ["crm_production_plan_revisions.id"],
            name=op.f(
                "fk_crm_production_unit_events_production_plan_revision_id_crm_production_plan_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["production_unit_id"],
            ["crm_production_units.id"],
            name=op.f("fk_crm_production_unit_events_production_unit_id_crm_production_units"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_production_unit_events")),
        sa.UniqueConstraint("event_key", name="uq_crm_production_unit_event_key"),
        sa.UniqueConstraint(
            "production_unit_id",
            "version",
            name="uq_crm_production_unit_event_version",
        ),
    )
    for column in (
        "actor_user_id",
        "event_type",
        "occurred_at",
        "production_plan_revision_id",
        "production_unit_id",
        "to_status",
    ):
        op.create_index(
            op.f(f"ix_crm_production_unit_events_{column}"),
            "crm_production_unit_events",
            [column],
        )

    op.execute(
        sa.text(
            "INSERT INTO crm_production_unit_events "
            "(production_unit_id, event_key, version, event_type, from_status, to_status, "
            "production_plan_revision_id, reason_code, actor_user_id, occurred_at) "
            "SELECT id, 'unit:' || CAST(id AS VARCHAR) || ':version:1', "
            "1, 'initialized', NULL, status, "
            "NULL, 'paid_order_intake', NULL, created_at FROM crm_production_units"
        )
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        changed = bind.execute(
            sa.text(
                "SELECT "
                "(SELECT count(*) FROM crm_production_plan_revisions) + "
                "(SELECT count(*) FROM crm_production_unit_events "
                " WHERE event_type <> 'initialized') + "
                "(SELECT count(*) FROM crm_production_units "
                " WHERE version <> 1 OR status <> 'queued' "
                " OR started_at IS NOT NULL OR closed_at IS NOT NULL)"
            )
        ).scalar_one()
        if changed:
            raise RuntimeError("Cannot downgrade CRM production workflow while evidence exists")

    for index_name in (
        "ix_crm_production_unit_events_to_status",
        "ix_crm_production_unit_events_production_unit_id",
        "ix_crm_production_unit_events_production_plan_revision_id",
        "ix_crm_production_unit_events_occurred_at",
        "ix_crm_production_unit_events_event_type",
        "ix_crm_production_unit_events_actor_user_id",
    ):
        op.drop_index(index_name, table_name="crm_production_unit_events")
    op.drop_table("crm_production_unit_events")
    for index_name in (
        "uq_crm_production_plan_active",
        "ix_crm_production_plan_revisions_tech_card_revision_id",
        "ix_crm_production_plan_revisions_status",
        "ix_crm_production_plan_revisions_production_unit_id",
        "ix_crm_production_plan_revisions_planned_by_user_id",
        "ix_crm_production_plan_revisions_planned_at",
        "ix_crm_production_plan_revisions_garment_size_id",
        "ix_crm_production_plan_revisions_garment_model_id",
        "ix_crm_production_plan_revisions_based_on_plan_revision_id",
    ):
        op.drop_index(index_name, table_name="crm_production_plan_revisions")
    op.drop_table("crm_production_plan_revisions")
    op.drop_constraint(
        op.f("ck_crm_production_units_crm_production_unit_lifecycle_timestamps_consistent"),
        "crm_production_units",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_crm_production_units_crm_production_unit_version_positive"),
        "crm_production_units",
        type_="check",
    )
    op.drop_column("crm_production_units", "closed_at")
    op.drop_column("crm_production_units", "started_at")
    op.drop_column("crm_production_units", "version")
