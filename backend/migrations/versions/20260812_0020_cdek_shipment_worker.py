"""Add durable CDEK shipment creation attempts.

Revision ID: 20260812_0020
Revises: 20260812_0019
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0020"
down_revision: str | Sequence[str] | None = "20260812_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cdek_shipment_attempts",
        sa.Column("shipment_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider_uuid", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(status = 'processing' AND completed_at IS NULL) OR "
            "(status <> 'processing' AND completed_at IS NOT NULL)",
            name=op.f("ck_cdek_shipment_attempts_cdek_shipment_attempt_completion_consistent"),
        ),
        sa.CheckConstraint(
            "attempt_number > 0",
            name=op.f("ck_cdek_shipment_attempts_cdek_shipment_attempt_number_positive"),
        ),
        sa.CheckConstraint(
            "length(request_sha256) = 64",
            name=op.f("ck_cdek_shipment_attempts_cdek_shipment_attempt_request_digest_length"),
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'retry', 'unknown', 'created', 'dead')",
            name=op.f("ck_cdek_shipment_attempts_cdek_shipment_attempt_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["shipment_id"],
            ["cdek_shipments.id"],
            name=op.f("fk_cdek_shipment_attempts_shipment_id_cdek_shipments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cdek_shipment_attempts")),
        sa.UniqueConstraint(
            "shipment_id",
            "attempt_number",
            name="uq_cdek_shipment_attempt_number",
        ),
    )
    op.create_index(
        op.f("ix_cdek_shipment_attempts_shipment_id"),
        "cdek_shipment_attempts",
        ["shipment_id"],
    )
    op.create_index(
        op.f("ix_cdek_shipment_attempts_started_at"),
        "cdek_shipment_attempts",
        ["started_at"],
    )
    op.create_index(
        op.f("ix_cdek_shipment_attempts_status"),
        "cdek_shipment_attempts",
        ["status"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        attempts = bind.execute(sa.text("SELECT count(*) FROM cdek_shipment_attempts")).scalar_one()
        if attempts:
            raise RuntimeError("Cannot downgrade CDEK worker while attempt evidence exists")

    op.drop_index(
        op.f("ix_cdek_shipment_attempts_status"),
        table_name="cdek_shipment_attempts",
    )
    op.drop_index(
        op.f("ix_cdek_shipment_attempts_started_at"),
        table_name="cdek_shipment_attempts",
    )
    op.drop_index(
        op.f("ix_cdek_shipment_attempts_shipment_id"),
        table_name="cdek_shipment_attempts",
    )
    op.drop_table("cdek_shipment_attempts")
