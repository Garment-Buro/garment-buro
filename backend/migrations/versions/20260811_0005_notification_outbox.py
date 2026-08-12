"""Add encrypted transactional notification outbox.

Revision ID: 20260811_0005
Revises: 20260811_0004
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0005"
down_revision: str | Sequence[str] | None = "20260811_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox",
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("template", sa.String(length=64), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=True),
        sa.Column("payload_nonce", sa.String(length=32), nullable=True),
        sa.Column("payload_tag", sa.String(length=32), nullable=True),
        sa.Column("encryption_key_version", sa.Integer(), nullable=False),
        sa.Column("deduplication_key", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("attempts_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('sent', 'dead') OR "
            "(payload_ciphertext IS NOT NULL AND payload_nonce IS NOT NULL "
            "AND payload_tag IS NOT NULL)",
            name=op.f("ck_notification_outbox_notification_outbox_active_payload_present"),
        ),
        sa.CheckConstraint(
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name=op.f("ck_notification_outbox_notification_outbox_attempts_valid"),
        ),
        sa.CheckConstraint(
            "channel IN ('email')",
            name=op.f("ck_notification_outbox_notification_outbox_channel_valid"),
        ),
        sa.CheckConstraint(
            "encryption_key_version > 0",
            name=op.f("ck_notification_outbox_notification_outbox_key_version_positive"),
        ),
        sa.CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 20",
            name=op.f("ck_notification_outbox_notification_outbox_max_attempts_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'retry', 'sent', 'dead')",
            name=op.f("ck_notification_outbox_notification_outbox_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_outbox")),
        sa.UniqueConstraint(
            "deduplication_key",
            name="uq_notification_outbox_deduplication_key",
        ),
    )
    op.create_index(
        op.f("ix_notification_outbox_available_at"),
        "notification_outbox",
        ["available_at"],
    )
    op.create_index(
        op.f("ix_notification_outbox_channel"),
        "notification_outbox",
        ["channel"],
    )
    op.create_index(
        op.f("ix_notification_outbox_locked_at"),
        "notification_outbox",
        ["locked_at"],
    )
    op.create_index(
        op.f("ix_notification_outbox_status"),
        "notification_outbox",
        ["status"],
    )
    op.create_index(
        op.f("ix_notification_outbox_template"),
        "notification_outbox",
        ["template"],
    )

    op.create_table(
        "notification_delivery_attempts",
        sa.Column("notification_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "attempt_number > 0",
            name=op.f("ck_notification_delivery_attempts_notification_attempt_number_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'retry', 'sent', 'dead', 'abandoned')",
            name=op.f("ck_notification_delivery_attempts_notification_attempt_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notification_outbox.id"],
            name=op.f("fk_notification_delivery_attempts_notification_id_notification_outbox"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_delivery_attempts")),
        sa.UniqueConstraint(
            "notification_id",
            "attempt_number",
            name="uq_notification_delivery_attempt_number",
        ),
    )
    op.create_index(
        op.f("ix_notification_delivery_attempts_notification_id"),
        "notification_delivery_attempts",
        ["notification_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notification_delivery_attempts_notification_id"),
        table_name="notification_delivery_attempts",
    )
    op.drop_table("notification_delivery_attempts")
    op.drop_index(op.f("ix_notification_outbox_template"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_status"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_locked_at"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_channel"), table_name="notification_outbox")
    op.drop_index(
        op.f("ix_notification_outbox_available_at"),
        table_name="notification_outbox",
    )
    op.drop_table("notification_outbox")
