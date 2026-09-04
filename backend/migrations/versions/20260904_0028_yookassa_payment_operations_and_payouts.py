"""Add YooKassa two-stage payment operations and payouts.

Revision ID: 20260904_0028
Revises: 20260812_0027
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260904_0028"
down_revision: str | Sequence[str] | None = "20260812_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payment_attempts",
        sa.Column(
            "capture_mode",
            sa.String(length=16),
            server_default=sa.text("'automatic'"),
            nullable=False,
        ),
    )
    op.add_column(
        "payment_attempts",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_payment_attempts_payment_attempt_capture_mode_valid"),
        "payment_attempts",
        "capture_mode IN ('automatic', 'manual')",
    )

    op.create_table(
        "payment_operations",
        sa.Column("payment_attempt_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("operation_type", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'prepared'"),
            nullable=False,
        ),
        sa.Column("client_key_digest_sha256", sa.String(length=64), nullable=False),
        sa.Column("provider_idempotence_key", sa.String(length=36), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("attempts_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            "attempts_count > 0",
            name=op.f("ck_payment_operations_payment_operation_attempts_positive"),
        ),
        sa.CheckConstraint(
            "length(client_key_digest_sha256) = 64",
            name=op.f("ck_payment_operations_payment_operation_client_digest_length"),
        ),
        sa.CheckConstraint(
            "last_attempt_at >= started_at",
            name=op.f("ck_payment_operations_payment_operation_attempt_time_valid"),
        ),
        sa.CheckConstraint(
            "length(provider_idempotence_key) = 36",
            name=op.f("ck_payment_operations_payment_operation_provider_key_length"),
        ),
        sa.CheckConstraint(
            "length(request_sha256) = 64",
            name=op.f("ck_payment_operations_payment_operation_request_digest_length"),
        ),
        sa.CheckConstraint(
            "(status IN ('succeeded', 'failed') AND resolved_at IS NOT NULL) OR "
            "(status NOT IN ('succeeded', 'failed') AND resolved_at IS NULL)",
            name=op.f("ck_payment_operations_payment_operation_resolution_consistent"),
        ),
        sa.CheckConstraint(
            "status IN ('prepared', 'unknown', 'succeeded', 'failed')",
            name=op.f("ck_payment_operations_payment_operation_status_valid"),
        ),
        sa.CheckConstraint(
            "operation_type IN ('capture', 'cancel')",
            name=op.f("ck_payment_operations_payment_operation_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_payment_operations_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id"],
            ["payment_attempts.id"],
            name=op.f("fk_payment_operations_payment_attempt_id_payment_attempts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_operations")),
        sa.UniqueConstraint(
            "client_key_digest_sha256",
            name="uq_payment_operation_client_key_digest",
        ),
        sa.UniqueConstraint(
            "payment_attempt_id",
            name="uq_payment_operation_attempt",
        ),
        sa.UniqueConstraint(
            "provider_idempotence_key",
            name="uq_payment_operation_provider_idempotence_key",
        ),
    )
    op.create_index(
        op.f("ix_payment_operations_actor_user_id"),
        "payment_operations",
        ["actor_user_id"],
    )
    op.create_index(
        op.f("ix_payment_operations_payment_attempt_id"),
        "payment_operations",
        ["payment_attempt_id"],
    )
    op.create_index(
        op.f("ix_payment_operations_status"),
        "payment_operations",
        ["status"],
    )

    op.create_table(
        "payouts",
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("client_key_digest_sha256", sa.String(length=64), nullable=False),
        sa.Column("provider_idempotence_key", sa.String(length=36), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'RUB'"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=True),
        sa.Column("requested_destination_type", sa.String(length=32), nullable=False),
        sa.Column("provider_destination_type", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'prepared'"),
            nullable=False,
        ),
        sa.Column("provider_payout_id", sa.String(length=50), nullable=True),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("test", sa.Boolean(), nullable=True),
        sa.Column("attempts_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_party", sa.String(length=32), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=64), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("provider_evidence_sha256", sa.String(length=64), nullable=True),
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
        sa.CheckConstraint("amount > 0", name=op.f("ck_payouts_payout_amount_positive")),
        sa.CheckConstraint(
            "(attempts_count = 0 AND last_attempt_at IS NULL) OR "
            "(attempts_count > 0 AND last_attempt_at IS NOT NULL)",
            name=op.f("ck_payouts_payout_attempt_state_consistent"),
        ),
        sa.CheckConstraint(
            "attempts_count >= 0",
            name=op.f("ck_payouts_payout_attempts_nonnegative"),
        ),
        sa.CheckConstraint(
            "(status = 'canceled' AND cancellation_party IS NOT NULL "
            "AND cancellation_reason IS NOT NULL) OR "
            "(status <> 'canceled' AND cancellation_party IS NULL "
            "AND cancellation_reason IS NULL)",
            name=op.f("ck_payouts_payout_cancellation_consistent"),
        ),
        sa.CheckConstraint(
            "length(client_key_digest_sha256) = 64",
            name=op.f("ck_payouts_payout_client_digest_length"),
        ),
        sa.CheckConstraint("currency = 'RUB'", name=op.f("ck_payouts_payout_currency_rub")),
        sa.CheckConstraint(
            "provider_destination_type IS NULL OR "
            "provider_destination_type IN ('bank_card', 'yoo_money', 'sbp')",
            name=op.f("ck_payouts_payout_provider_destination_valid"),
        ),
        sa.CheckConstraint(
            "length(provider_idempotence_key) = 36",
            name=op.f("ck_payouts_payout_provider_key_length"),
        ),
        sa.CheckConstraint(
            "requested_destination_type IN "
            "('payout_token', 'payment_method', 'bank_card', 'yoo_money', 'sbp')",
            name=op.f("ck_payouts_payout_requested_destination_valid"),
        ),
        sa.CheckConstraint(
            "request_sha256 IS NULL OR length(request_sha256) = 64",
            name=op.f("ck_payouts_payout_request_digest_length"),
        ),
        sa.CheckConstraint(
            "(status IN ('failed', 'succeeded', 'canceled') AND resolved_at IS NOT NULL) OR "
            "(status NOT IN ('failed', 'succeeded', 'canceled') AND resolved_at IS NULL)",
            name=op.f("ck_payouts_payout_resolution_consistent"),
        ),
        sa.CheckConstraint(
            "status IN ('prepared', 'unknown', 'failed', 'pending', 'succeeded', 'canceled')",
            name=op.f("ck_payouts_payout_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_payouts_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payouts")),
        sa.UniqueConstraint(
            "client_key_digest_sha256",
            name=op.f("uq_payouts_client_key_digest_sha256"),
        ),
        sa.UniqueConstraint(
            "provider_idempotence_key",
            name=op.f("uq_payouts_provider_idempotence_key"),
        ),
        sa.UniqueConstraint(
            "provider_payout_id",
            name=op.f("uq_payouts_provider_payout_id"),
        ),
    )
    op.create_index(op.f("ix_payouts_actor_user_id"), "payouts", ["actor_user_id"])
    op.create_index(op.f("ix_payouts_reference"), "payouts", ["reference"])
    op.create_index(op.f("ix_payouts_status"), "payouts", ["status"])

    _grant_financial_permissions()


def _grant_financial_permissions() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO permissions (code, description, created_at, updated_at) "
            "VALUES (:code, :description, now(), now()) ON CONFLICT (code) DO NOTHING"
        ),
        [
            {"code": "payments.manage", "description": "Manage payment capture and cancel"},
            {"code": "payouts.manage", "description": "Create and reconcile payouts"},
        ],
    )
    bind.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id, created_at) "
            "SELECT roles.id, permissions.id, now() FROM roles CROSS JOIN permissions "
            "WHERE (roles.name = 'manager' AND permissions.code = 'payments.manage') "
            "OR (roles.name = 'admin' AND permissions.code IN "
            "('payments.manage', 'payouts.manage')) ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        if bind.execute(sa.text("SELECT count(*) FROM payment_operations")).scalar_one():
            raise RuntimeError("Cannot downgrade while payment operation records exist")
        if bind.execute(sa.text("SELECT count(*) FROM payouts")).scalar_one():
            raise RuntimeError("Cannot downgrade while payout records exist")
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code IN ('payments.manage', 'payouts.manage'))"
    )
    op.execute("DELETE FROM permissions WHERE code IN ('payments.manage', 'payouts.manage')")
    op.drop_index(op.f("ix_payouts_status"), table_name="payouts")
    op.drop_index(op.f("ix_payouts_reference"), table_name="payouts")
    op.drop_index(op.f("ix_payouts_actor_user_id"), table_name="payouts")
    op.drop_table("payouts")
    op.drop_index(op.f("ix_payment_operations_status"), table_name="payment_operations")
    op.drop_index(
        op.f("ix_payment_operations_payment_attempt_id"),
        table_name="payment_operations",
    )
    op.drop_index(
        op.f("ix_payment_operations_actor_user_id"),
        table_name="payment_operations",
    )
    op.drop_table("payment_operations")
    op.drop_constraint(
        op.f("ck_payment_attempts_payment_attempt_capture_mode_valid"),
        "payment_attempts",
        type_="check",
    )
    op.drop_column("payment_attempts", "expires_at")
    op.drop_column("payment_attempts", "capture_mode")
