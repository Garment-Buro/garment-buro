"""Add reusable content and template selection to partner landings.

Revision ID: 20260904_0030
Revises: 20260904_0029
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260904_0030"
down_revision: str | Sequence[str] | None = "20260904_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "partner_landings",
        sa.Column(
            "template_key",
            sa.String(length=32),
            server_default=sa.text("'light-running'"),
            nullable=False,
        ),
    )
    op.add_column(
        "partner_landings",
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("partner_landings", "content")
    op.drop_column("partner_landings", "template_key")
