"""Add immutable catalog write audit events.

Revision ID: 20260811_0007
Revises: 20260811_0006
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0007"
down_revision: str | Sequence[str] | None = "20260811_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "media_objects",
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_media_objects_uploaded_by_user_id_users"),
        "media_objects",
        "users",
        ["uploaded_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_media_objects_uploaded_by_user_id"),
        "media_objects",
        ["uploaded_by_user_id"],
    )

    op.create_table(
        "catalog_audit_events",
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('product.created', 'product.updated', 'product.deleted')",
            name=op.f("ck_catalog_audit_events_catalog_audit_action_valid"),
        ),
        sa.CheckConstraint(
            "length(snapshot_checksum_sha256) = 64",
            name=op.f("ck_catalog_audit_events_catalog_audit_snapshot_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_catalog_audit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_audit_events")),
    )
    op.create_index(
        op.f("ix_catalog_audit_events_action"),
        "catalog_audit_events",
        ["action"],
    )
    op.create_index(
        op.f("ix_catalog_audit_events_actor_user_id"),
        "catalog_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        op.f("ix_catalog_audit_events_created_at"),
        "catalog_audit_events",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_catalog_audit_events_product_id"),
        "catalog_audit_events",
        ["product_id"],
    )

    op.create_table(
        "catalog_documents",
        sa.Column("document_key", sa.String(length=32), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
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
            "document_key IN ('settings', 'options')",
            name=op.f("ck_catalog_documents_catalog_document_key_valid"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_catalog_documents_catalog_document_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_catalog_documents_updated_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("document_key", name=op.f("pk_catalog_documents")),
    )
    op.create_index(
        op.f("ix_catalog_documents_updated_by_user_id"),
        "catalog_documents",
        ["updated_by_user_id"],
    )

    op.create_table(
        "catalog_document_revisions",
        sa.Column("document_key", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "document_key IN ('settings', 'options')",
            name=op.f("ck_catalog_document_revisions_catalog_document_revision_key_valid"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_catalog_document_revisions_catalog_document_revision_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_catalog_document_revisions_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_document_revisions")),
        sa.UniqueConstraint(
            "document_key",
            "version",
            name="uq_catalog_document_revision_key_version",
        ),
    )
    op.create_index(
        op.f("ix_catalog_document_revisions_actor_user_id"),
        "catalog_document_revisions",
        ["actor_user_id"],
    )
    op.create_index(
        op.f("ix_catalog_document_revisions_created_at"),
        "catalog_document_revisions",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_catalog_document_revisions_document_key"),
        "catalog_document_revisions",
        ["document_key"],
    )

    op.create_table(
        "catalog_content_migration_runs",
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("documents_count", sa.Integer(), nullable=False),
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
            "documents_count >= 0",
            name=op.f(
                "ck_catalog_content_migration_runs_catalog_content_run_documents_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "length(fingerprint_sha256) = 64",
            name=op.f("ck_catalog_content_migration_runs_catalog_content_run_fingerprint_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_content_migration_runs")),
        sa.UniqueConstraint(
            "fingerprint_sha256",
            name=op.f("uq_catalog_content_migration_runs_fingerprint_sha256"),
        ),
    )


def downgrade() -> None:
    op.drop_table("catalog_content_migration_runs")
    op.drop_index(
        op.f("ix_catalog_document_revisions_document_key"),
        table_name="catalog_document_revisions",
    )
    op.drop_index(
        op.f("ix_catalog_document_revisions_created_at"),
        table_name="catalog_document_revisions",
    )
    op.drop_index(
        op.f("ix_catalog_document_revisions_actor_user_id"),
        table_name="catalog_document_revisions",
    )
    op.drop_table("catalog_document_revisions")
    op.drop_index(
        op.f("ix_catalog_documents_updated_by_user_id"),
        table_name="catalog_documents",
    )
    op.drop_table("catalog_documents")
    op.drop_index(
        op.f("ix_catalog_audit_events_product_id"),
        table_name="catalog_audit_events",
    )
    op.drop_index(
        op.f("ix_catalog_audit_events_created_at"),
        table_name="catalog_audit_events",
    )
    op.drop_index(
        op.f("ix_catalog_audit_events_actor_user_id"),
        table_name="catalog_audit_events",
    )
    op.drop_index(
        op.f("ix_catalog_audit_events_action"),
        table_name="catalog_audit_events",
    )
    op.drop_table("catalog_audit_events")
    op.drop_index(
        op.f("ix_media_objects_uploaded_by_user_id"),
        table_name="media_objects",
    )
    op.drop_constraint(
        op.f("fk_media_objects_uploaded_by_user_id_users"),
        "media_objects",
        type_="foreignkey",
    )
    op.drop_column("media_objects", "uploaded_by_user_id")
