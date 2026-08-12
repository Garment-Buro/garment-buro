"""Record verified catalog imports for guarded read cutover.

Revision ID: 20260811_0003
Revises: 20260811_0002
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0003"
down_revision: str | Sequence[str] | None = "20260811_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_migration_runs",
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("products_count", sa.Integer(), nullable=False),
        sa.Column("variants_count", sa.Integer(), nullable=False),
        sa.Column("media_count", sa.Integer(), nullable=False),
        sa.Column("media_references_count", sa.Integer(), nullable=False),
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
            "length(fingerprint_sha256) = 64",
            name=op.f("ck_catalog_migration_runs_catalog_run_fingerprint_length"),
        ),
        sa.CheckConstraint(
            "media_count >= 0",
            name=op.f("ck_catalog_migration_runs_catalog_run_media_nonnegative"),
        ),
        sa.CheckConstraint(
            "media_references_count >= 0",
            name=op.f("ck_catalog_migration_runs_catalog_run_media_references_nonnegative"),
        ),
        sa.CheckConstraint(
            "products_count >= 0",
            name=op.f("ck_catalog_migration_runs_catalog_run_products_nonnegative"),
        ),
        sa.CheckConstraint(
            "variants_count >= 0",
            name=op.f("ck_catalog_migration_runs_catalog_run_variants_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_migration_runs")),
        sa.UniqueConstraint(
            "fingerprint_sha256",
            name=op.f("uq_catalog_migration_runs_fingerprint_sha256"),
        ),
    )


def downgrade() -> None:
    op.drop_table("catalog_migration_runs")
