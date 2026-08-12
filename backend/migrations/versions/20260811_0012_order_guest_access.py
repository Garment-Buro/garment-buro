"""Add hashed guest order access capabilities.

Revision ID: 20260811_0012
Revises: 20260811_0011
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0012"
down_revision: str | Sequence[str] | None = "20260811_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_guest_access",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("token_digest_sha256", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            "expires_at > created_at",
            name=op.f("ck_order_guest_access_order_guest_access_expiry_after_creation"),
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name=op.f("ck_order_guest_access_order_guest_access_revocation_after_creation"),
        ),
        sa.CheckConstraint(
            "length(token_digest_sha256) = 64",
            name=op.f("ck_order_guest_access_order_guest_access_token_digest_length"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_guest_access_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_guest_access")),
        sa.UniqueConstraint("order_id", name=op.f("uq_order_guest_access_order_id")),
        sa.UniqueConstraint(
            "token_digest_sha256",
            name=op.f("uq_order_guest_access_token_digest_sha256"),
        ),
    )
    op.create_index(
        op.f("ix_order_guest_access_expires_at"),
        "order_guest_access",
        ["expires_at"],
    )
    op.create_index(
        op.f("ix_order_guest_access_order_id"),
        "order_guest_access",
        ["order_id"],
    )
    op.create_index(
        op.f("ix_order_guest_access_token_digest_sha256"),
        "order_guest_access",
        ["token_digest_sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_order_guest_access_token_digest_sha256"),
        table_name="order_guest_access",
    )
    op.drop_index(
        op.f("ix_order_guest_access_order_id"),
        table_name="order_guest_access",
    )
    op.drop_index(
        op.f("ix_order_guest_access_expires_at"),
        table_name="order_guest_access",
    )
    op.drop_table("order_guest_access")
