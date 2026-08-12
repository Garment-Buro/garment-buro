"""Establish the async PostgreSQL migration baseline.

Revision ID: 20260811_0001
Revises:
Create Date: 2026-08-11
"""

from collections.abc import Sequence

revision: str = "20260811_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Domain tables are introduced by subsequent module migrations."""


def downgrade() -> None:
    """The baseline contains no domain objects to remove."""
