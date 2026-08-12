"""Add private CRM file attachment metadata.

Revision ID: 20260812_0025
Revises: 20260812_0024
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0025"
down_revision: str | Sequence[str] | None = "20260812_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_file_attachments",
        sa.Column("media_object_id", sa.Integer(), nullable=False),
        sa.Column("tech_card_revision_id", sa.Integer(), nullable=True),
        sa.Column("production_project_id", sa.Integer(), nullable=True),
        sa.Column("production_unit_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "role IN ('pattern', 'tech_card_source', 'production_evidence')",
            name=op.f("ck_crm_file_attachments_crm_file_role_valid"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_crm_file_attachments_crm_file_sort_order_nonnegative"),
        ),
        sa.CheckConstraint(
            "(tech_card_revision_id IS NOT NULL AND production_project_id IS NULL "
            "AND production_unit_id IS NULL) OR "
            "(tech_card_revision_id IS NULL AND production_project_id IS NOT NULL "
            "AND production_unit_id IS NULL) OR "
            "(tech_card_revision_id IS NULL AND production_project_id IS NULL "
            "AND production_unit_id IS NOT NULL)",
            name=op.f("ck_crm_file_attachments_crm_file_exactly_one_target"),
        ),
        sa.CheckConstraint(
            "(tech_card_revision_id IS NOT NULL AND role IN ('pattern', 'tech_card_source')) OR "
            "((production_project_id IS NOT NULL OR production_unit_id IS NOT NULL) "
            "AND role = 'production_evidence')",
            name=op.f("ck_crm_file_attachments_crm_file_role_target_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["media_object_id"],
            ["media_objects.id"],
            name=op.f("fk_crm_file_attachments_media_object_id_media_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["production_project_id"],
            ["crm_order_projects.id"],
            name=op.f("fk_crm_file_attachments_production_project_id_crm_order_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["production_unit_id"],
            ["crm_production_units.id"],
            name=op.f("fk_crm_file_attachments_production_unit_id_crm_production_units"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tech_card_revision_id"],
            ["crm_tech_card_revisions.id"],
            name=op.f("fk_crm_file_attachments_tech_card_revision_id_crm_tech_card_revisions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name=op.f("fk_crm_file_attachments_uploaded_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_file_attachments")),
        sa.UniqueConstraint(
            "media_object_id", name=op.f("uq_crm_file_attachments_media_object_id")
        ),
        sa.UniqueConstraint(
            "tech_card_revision_id",
            "role",
            "sort_order",
            name="uq_crm_file_tech_card_role_order",
        ),
        sa.UniqueConstraint(
            "production_project_id",
            "role",
            "sort_order",
            name="uq_crm_file_project_role_order",
        ),
        sa.UniqueConstraint(
            "production_unit_id",
            "role",
            "sort_order",
            name="uq_crm_file_unit_role_order",
        ),
    )
    for column in (
        "media_object_id",
        "production_project_id",
        "production_unit_id",
        "role",
        "tech_card_revision_id",
        "uploaded_by_user_id",
    ):
        op.create_index(op.f(f"ix_crm_file_attachments_{column}"), "crm_file_attachments", [column])

    op.create_table(
        "crm_file_access_events",
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "event_type = 'download_url_issued'",
            name=op.f("ck_crm_file_access_events_crm_file_access_event_type_valid"),
        ),
        sa.CheckConstraint(
            "expires_at > occurred_at",
            name=op.f("ck_crm_file_access_events_crm_file_access_event_expiry_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_crm_file_access_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["crm_file_attachments.id"],
            name=op.f("fk_crm_file_access_events_attachment_id_crm_file_attachments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_file_access_events")),
    )
    for column in ("actor_user_id", "attachment_id", "event_type", "occurred_at"):
        op.create_index(
            op.f(f"ix_crm_file_access_events_{column}"),
            "crm_file_access_events",
            [column],
        )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        attachments = connection.execute(
            sa.text("SELECT count(*) FROM crm_file_attachments")
        ).scalar_one()
        access_events = connection.execute(
            sa.text("SELECT count(*) FROM crm_file_access_events")
        ).scalar_one()
        if attachments or access_events:
            raise RuntimeError("Cannot downgrade CRM private files while attachments exist")
    for name in (
        "ix_crm_file_access_events_occurred_at",
        "ix_crm_file_access_events_event_type",
        "ix_crm_file_access_events_attachment_id",
        "ix_crm_file_access_events_actor_user_id",
    ):
        op.drop_index(name, table_name="crm_file_access_events")
    op.drop_table("crm_file_access_events")
    for name in (
        "ix_crm_file_attachments_uploaded_by_user_id",
        "ix_crm_file_attachments_tech_card_revision_id",
        "ix_crm_file_attachments_role",
        "ix_crm_file_attachments_production_unit_id",
        "ix_crm_file_attachments_production_project_id",
        "ix_crm_file_attachments_media_object_id",
    ):
        op.drop_index(name, table_name="crm_file_attachments")
    op.drop_table("crm_file_attachments")
