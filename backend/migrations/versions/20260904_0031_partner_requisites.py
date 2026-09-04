"""Add encrypted partner payout requisites.

Revision ID: 20260904_0031
Revises: 20260904_0030
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0031"
down_revision: str | Sequence[str] | None = "20260904_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "partner_requisites",
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
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
            "key_version > 0",
            name=op.f("ck_partner_requisites_partner_requisites_key_version_positive"),
        ),
        sa.CheckConstraint(
            "length(payload_sha256) = 64",
            name=op.f("ck_partner_requisites_partner_requisites_payload_sha256_length"),
        ),
        sa.CheckConstraint(
            "schema_version > 0",
            name=op.f("ck_partner_requisites_partner_requisites_schema_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partner_profiles.id"],
            name=op.f("fk_partner_requisites_partner_id_partner_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_requisites")),
        sa.UniqueConstraint("partner_id", name=op.f("uq_partner_requisites_partner_id")),
    )
    op.create_index(
        op.f("ix_partner_requisites_partner_id"),
        "partner_requisites",
        ["partner_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_partner_requisites_partner_id"),
        table_name="partner_requisites",
    )
    op.drop_table("partner_requisites")
