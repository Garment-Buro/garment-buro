"""Add password and external authentication with multi-channel notifications.

Revision ID: 20260904_0032
Revises: 20260904_0031
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0032"
down_revision: str | Sequence[str] | None = "20260904_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_normalized", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("primary_auth_provider", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("primary_auth_subject", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_users_phone_normalized"), "users", ["phone_normalized"], unique=True)
    op.create_unique_constraint(
        "uq_users_primary_auth_identity",
        "users",
        ["primary_auth_provider", "primary_auth_subject"],
    )
    op.execute(
        sa.text(
            "UPDATE users SET primary_auth_provider = 'telegram', "
            "primary_auth_subject = telegram_id "
            "WHERE email_normalized IS NULL AND telegram_id IS NOT NULL"
        )
    )
    op.drop_constraint(op.f("ck_users_user_identifier_present"), "users", type_="check")
    op.create_check_constraint(
        op.f("ck_users_user_identifier_present"),
        "users",
        "status = 'deleted' OR email_normalized IS NOT NULL "
        "OR phone_normalized IS NOT NULL OR primary_auth_subject IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_users_user_phone_normalized_requires_phone"),
        "users",
        "phone_normalized IS NULL OR phone IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_users_user_primary_auth_pair_consistent"),
        "users",
        "(primary_auth_provider IS NULL) = (primary_auth_subject IS NULL)",
    )

    op.create_table(
        "password_credentials",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("algorithm", sa.String(length=32), server_default="argon2id", nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
            "algorithm = 'argon2id'",
            name=op.f("ck_password_credentials_password_algorithm_valid"),
        ),
        sa.CheckConstraint(
            "failed_attempts >= 0",
            name=op.f("ck_password_credentials_password_failed_attempts_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_credentials")),
        sa.UniqueConstraint("user_id", name=op.f("uq_password_credentials_user_id")),
    )
    op.create_index(
        op.f("ix_password_credentials_locked_until"),
        "password_credentials",
        ["locked_until"],
    )
    op.create_index(
        op.f("ix_password_credentials_user_id"),
        "password_credentials",
        ["user_id"],
    )

    op.create_table(
        "external_auth_identities",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_external_auth_identities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_auth_identities")),
        sa.UniqueConstraint(
            "provider",
            "subject",
            name="uq_external_auth_identity_provider_subject",
        ),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            name="uq_external_auth_identity_user_provider",
        ),
    )
    op.create_index(
        op.f("ix_external_auth_identities_provider"),
        "external_auth_identities",
        ["provider"],
    )
    op.create_index(
        op.f("ix_external_auth_identities_user_id"),
        "external_auth_identities",
        ["user_id"],
    )
    op.execute(
        sa.text(
            "INSERT INTO external_auth_identities "
            "(user_id, provider, subject, verified_at, created_at, updated_at) "
            "SELECT id, 'telegram', telegram_id, COALESCE(created_at, CURRENT_TIMESTAMP), "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM users WHERE telegram_id IS NOT NULL"
        )
    )

    op.add_column(
        "otp_challenges",
        sa.Column("method", sa.String(length=16), server_default="email", nullable=False),
    )
    op.add_column("otp_challenges", sa.Column("target_value", sa.String(length=320)))
    op.add_column("otp_challenges", sa.Column("target_normalized", sa.String(length=320)))
    op.execute(
        sa.text(
            "UPDATE otp_challenges SET target_value = target_email, "
            "target_normalized = target_email_normalized"
        )
    )
    op.create_check_constraint(
        op.f("ck_otp_challenges_otp_challenge_method_valid"),
        "otp_challenges",
        "method IN ('email', 'phone')",
    )
    op.create_index(op.f("ix_otp_challenges_method"), "otp_challenges", ["method"])
    op.create_index(
        op.f("ix_otp_challenges_target_normalized"),
        "otp_challenges",
        ["target_normalized"],
    )

    op.drop_constraint(
        op.f("ck_notification_outbox_notification_outbox_channel_valid"),
        "notification_outbox",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_notification_outbox_notification_outbox_channel_valid"),
        "notification_outbox",
        "channel IN ('email', 'telegram', 'phone')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_notification_outbox_notification_outbox_channel_valid"),
        "notification_outbox",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_notification_outbox_notification_outbox_channel_valid"),
        "notification_outbox",
        "channel IN ('email')",
    )

    op.drop_index(op.f("ix_otp_challenges_target_normalized"), table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_method"), table_name="otp_challenges")
    op.drop_constraint(
        op.f("ck_otp_challenges_otp_challenge_method_valid"),
        "otp_challenges",
        type_="check",
    )
    op.drop_column("otp_challenges", "target_normalized")
    op.drop_column("otp_challenges", "target_value")
    op.drop_column("otp_challenges", "method")

    op.drop_index(
        op.f("ix_external_auth_identities_user_id"), table_name="external_auth_identities"
    )
    op.drop_index(
        op.f("ix_external_auth_identities_provider"), table_name="external_auth_identities"
    )
    op.drop_table("external_auth_identities")
    op.drop_index(op.f("ix_password_credentials_user_id"), table_name="password_credentials")
    op.drop_index(op.f("ix_password_credentials_locked_until"), table_name="password_credentials")
    op.drop_table("password_credentials")

    op.drop_constraint(op.f("ck_users_user_identifier_present"), "users", type_="check")
    op.drop_constraint(
        op.f("ck_users_user_primary_auth_pair_consistent"),
        "users",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_users_user_phone_normalized_requires_phone"),
        "users",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_users_user_identifier_present"),
        "users",
        "status = 'deleted' OR email_normalized IS NOT NULL OR telegram_id IS NOT NULL",
    )
    op.drop_constraint("uq_users_primary_auth_identity", "users", type_="unique")
    op.drop_index(op.f("ix_users_phone_normalized"), table_name="users")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "primary_auth_subject")
    op.drop_column("users", "primary_auth_provider")
    op.drop_column("users", "phone_normalized")
