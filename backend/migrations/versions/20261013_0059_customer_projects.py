"""Persist versioned customer constructor documents and retain referenced media.

Revision ID: 20261013_0059
Revises: 20261013_0058
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261013_0059"
down_revision = "20261013_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("client_key", sa.String(100), nullable=False),
        sa.Column("creation_sha256", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "snapshot",
            sa.JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_projects")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_customer_projects_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="SET NULL",
            name=op.f("fk_customer_projects_product_id_products"),
        ),
        sa.UniqueConstraint("user_id", "client_key", name="uq_customer_projects_user_client_key"),
        sa.CheckConstraint(
            "kind IN ('draft', 'collection')",
            name=op.f("ck_customer_projects_customer_project_kind_valid"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_customer_projects_customer_project_version_positive")
        ),
        sa.CheckConstraint(
            "length(creation_sha256) = 64",
            name=op.f("ck_customer_projects_customer_project_creation_hash"),
        ),
        sa.CheckConstraint(
            "deleted_at IS NOT NULL OR snapshot IS NOT NULL",
            name=op.f("ck_customer_projects_customer_project_document_required"),
        ),
    )
    op.create_index(
        "ix_customer_projects_user_kind_recent",
        "customer_projects",
        ["user_id", "kind", "id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(op.f("ix_customer_projects_product_id"), "customer_projects", ["product_id"])
    op.create_table(
        "customer_project_media",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("media_object_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint(
            "project_id", "media_object_id", name=op.f("pk_customer_project_media")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["customer_projects.id"],
            ondelete="CASCADE",
            name=op.f("fk_customer_project_media_project_id_customer_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["media_object_id"],
            ["media_objects.id"],
            ondelete="RESTRICT",
            name=op.f("fk_customer_project_media_media_object_id_media_objects"),
        ),
    )
    op.create_index(
        op.f("ix_customer_project_media_media_object_id"),
        "customer_project_media",
        ["media_object_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_customer_project_media_media_object_id"), table_name="customer_project_media"
    )
    op.drop_table("customer_project_media")
    op.drop_index(op.f("ix_customer_projects_product_id"), table_name="customer_projects")
    op.drop_index("ix_customer_projects_user_kind_recent", table_name="customer_projects")
    op.drop_table("customer_projects")
