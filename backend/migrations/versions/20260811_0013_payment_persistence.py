"""Add durable payment attempts and webhook event intake.

Revision ID: 20260811_0013
Revises: 20260811_0012
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0013"
down_revision: str | Sequence[str] | None = "20260811_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default=sa.text("'yookassa'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'RUB'"),
            nullable=False,
        ),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
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
            "amount > 0",
            name=op.f("ck_payments_payment_amount_positive"),
        ),
        sa.CheckConstraint(
            "currency = 'RUB'",
            name=op.f("ck_payments_payment_currency_rub"),
        ),
        sa.CheckConstraint(
            "provider IN ('yookassa')",
            name=op.f("ck_payments_payment_provider_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'canceled')",
            name=op.f("ck_payments_payment_status_valid"),
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND succeeded_at IS NOT NULL) OR "
            "(status <> 'succeeded' AND succeeded_at IS NULL)",
            name=op.f("ck_payments_payment_success_timestamp_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_payments_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("order_id", name="uq_payments_order_id"),
    )
    op.create_index(op.f("ix_payments_order_id"), "payments", ["order_id"])
    op.create_index(op.f("ix_payments_provider"), "payments", ["provider"])
    op.create_index(op.f("ix_payments_status"), "payments", ["status"])

    op.create_table(
        "payment_attempts",
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("client_key_digest_sha256", sa.String(length=64), nullable=False),
        sa.Column("provider_idempotence_key", sa.String(length=36), nullable=False),
        sa.Column("request_fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'prepared'"),
            nullable=False,
        ),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("confirmation_url", sa.Text(), nullable=True),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_party", sa.String(length=64), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=128), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
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
            "length(client_key_digest_sha256) = 64",
            name=op.f("ck_payment_attempts_payment_attempt_client_digest_length"),
        ),
        sa.CheckConstraint(
            "length(request_fingerprint_sha256) = 64",
            name=op.f("ck_payment_attempts_payment_attempt_fingerprint_length"),
        ),
        sa.CheckConstraint(
            "payment_method IN ('bank_card', 'sbp')",
            name=op.f("ck_payment_attempts_payment_attempt_method_valid"),
        ),
        sa.CheckConstraint(
            "attempt_number > 0",
            name=op.f("ck_payment_attempts_payment_attempt_number_positive"),
        ),
        sa.CheckConstraint(
            "provider_payment_id IS NOT NULL OR status IN ('prepared', 'unknown')",
            name=op.f("ck_payment_attempts_payment_attempt_provider_id_present"),
        ),
        sa.CheckConstraint(
            "length(provider_idempotence_key) = 36",
            name=op.f("ck_payment_attempts_payment_attempt_provider_key_length"),
        ),
        sa.CheckConstraint(
            "(status IN ('succeeded', 'canceled') AND resolved_at IS NOT NULL "
            "AND resolved_at >= created_at) OR "
            "(status NOT IN ('succeeded', 'canceled') AND resolved_at IS NULL)",
            name=op.f("ck_payment_attempts_payment_attempt_resolution_after_creation"),
        ),
        sa.CheckConstraint(
            "(status = 'canceled' AND cancellation_party IS NOT NULL "
            "AND cancellation_reason IS NOT NULL) OR "
            "(status <> 'canceled' AND cancellation_party IS NULL "
            "AND cancellation_reason IS NULL)",
            name=op.f("ck_payment_attempts_payment_attempt_cancellation_consistent"),
        ),
        sa.CheckConstraint(
            "status IN ('prepared', 'unknown', 'pending', 'waiting_for_capture', "
            "'succeeded', 'canceled')",
            name=op.f("ck_payment_attempts_payment_attempt_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_attempts_payment_id_payments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_attempts")),
        sa.UniqueConstraint(
            "client_key_digest_sha256",
            name="uq_payment_attempt_client_key_digest",
        ),
        sa.UniqueConstraint(
            "payment_id",
            "attempt_number",
            name="uq_payment_attempt_number",
        ),
        sa.UniqueConstraint(
            "provider_idempotence_key",
            name="uq_payment_attempt_provider_idempotence_key",
        ),
        sa.UniqueConstraint(
            "provider_payment_id",
            name="uq_payment_attempt_provider_payment_id",
        ),
    )
    op.create_index(
        op.f("ix_payment_attempts_payment_id"),
        "payment_attempts",
        ["payment_id"],
    )
    op.create_index(
        op.f("ix_payment_attempts_status"),
        "payment_attempts",
        ["status"],
    )

    op.create_table(
        "payment_events",
        sa.Column("payment_attempt_id", sa.Integer(), nullable=True),
        sa.Column("event_key_sha256", sa.String(length=64), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("observation_sha256", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=False),
        sa.Column("observed_status", sa.String(length=32), nullable=False),
        sa.Column("observed_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("observed_currency", sa.String(length=3), nullable=False),
        sa.Column("observed_paid", sa.Boolean(), nullable=False),
        sa.Column("observed_test", sa.Boolean(), nullable=False),
        sa.Column("metadata_order_id", sa.Integer(), nullable=False),
        sa.Column("source_ip", sa.String(length=45), nullable=False),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_party", sa.String(length=64), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'received'"),
            nullable=False,
        ),
        sa.Column("attempts_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
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
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name=op.f("ck_payment_events_payment_event_attempts_valid"),
        ),
        sa.CheckConstraint(
            "observed_amount > 0",
            name=op.f("ck_payment_events_payment_event_amount_positive"),
        ),
        sa.CheckConstraint(
            "observed_currency = 'RUB'",
            name=op.f("ck_payment_events_payment_event_currency_rub"),
        ),
        sa.CheckConstraint(
            "length(event_key_sha256) = 64",
            name=op.f("ck_payment_events_payment_event_key_length"),
        ),
        sa.CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 20",
            name=op.f("ck_payment_events_payment_event_max_attempts_valid"),
        ),
        sa.CheckConstraint(
            "length(observation_sha256) = 64",
            name=op.f("ck_payment_events_payment_event_observation_digest_length"),
        ),
        sa.CheckConstraint(
            "observed_status IN ('waiting_for_capture', 'succeeded', 'canceled')",
            name=op.f("ck_payment_events_payment_event_observed_status_valid"),
        ),
        sa.CheckConstraint(
            "metadata_order_id > 0",
            name=op.f("ck_payment_events_payment_event_order_positive"),
        ),
        sa.CheckConstraint(
            "length(payload_sha256) = 64",
            name=op.f("ck_payment_events_payment_event_payload_digest_length"),
        ),
        sa.CheckConstraint(
            "status IN ('received', 'processing', 'retry', 'processed', 'rejected', 'dead')",
            name=op.f("ck_payment_events_payment_event_status_valid"),
        ),
        sa.CheckConstraint(
            "event_type IN ('payment.waiting_for_capture', 'payment.succeeded', "
            "'payment.canceled')",
            name=op.f("ck_payment_events_payment_event_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id"],
            ["payment_attempts.id"],
            name=op.f("fk_payment_events_payment_attempt_id_payment_attempts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
        sa.UniqueConstraint("event_key_sha256", name="uq_payment_event_key"),
    )
    op.create_index(
        op.f("ix_payment_events_available_at"),
        "payment_events",
        ["available_at"],
    )
    op.create_index(
        op.f("ix_payment_events_event_type"),
        "payment_events",
        ["event_type"],
    )
    op.create_index(
        op.f("ix_payment_events_locked_at"),
        "payment_events",
        ["locked_at"],
    )
    op.create_index(
        op.f("ix_payment_events_metadata_order_id"),
        "payment_events",
        ["metadata_order_id"],
    )
    op.create_index(
        op.f("ix_payment_events_payment_attempt_id"),
        "payment_events",
        ["payment_attempt_id"],
    )
    op.create_index(
        op.f("ix_payment_events_provider_payment_id"),
        "payment_events",
        ["provider_payment_id"],
    )
    op.create_index(op.f("ix_payment_events_status"), "payment_events", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_events_status"), table_name="payment_events")
    op.drop_index(
        op.f("ix_payment_events_provider_payment_id"),
        table_name="payment_events",
    )
    op.drop_index(
        op.f("ix_payment_events_payment_attempt_id"),
        table_name="payment_events",
    )
    op.drop_index(
        op.f("ix_payment_events_metadata_order_id"),
        table_name="payment_events",
    )
    op.drop_index(op.f("ix_payment_events_locked_at"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_event_type"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_available_at"), table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_index(op.f("ix_payment_attempts_status"), table_name="payment_attempts")
    op.drop_index(op.f("ix_payment_attempts_payment_id"), table_name="payment_attempts")
    op.drop_table("payment_attempts")
    op.drop_index(op.f("ix_payments_status"), table_name="payments")
    op.drop_index(op.f("ix_payments_provider"), table_name="payments")
    op.drop_index(op.f("ix_payments_order_id"), table_name="payments")
    op.drop_table("payments")
