"""Add identity persistence, RBAC, OTP, sessions, and security audit.

Revision ID: 20260811_0004
Revises: 20260811_0003
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0004"
down_revision: str | Sequence[str] | None = "20260811_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_normalized", sa.String(length=320), nullable=True),
        sa.Column("telegram_id", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("height_cm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "(email IS NULL) = (email_normalized IS NULL)",
            name=op.f("ck_users_user_email_pair_consistent"),
        ),
        sa.CheckConstraint(
            "height_cm IS NULL OR height_cm >= 0",
            name=op.f("ck_users_user_height_nonnegative"),
        ),
        sa.CheckConstraint(
            "email_normalized IS NOT NULL OR telegram_id IS NOT NULL",
            name=op.f("ck_users_user_identifier_present"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'blocked', 'deleted')",
            name=op.f("ck_users_user_status_valid"),
        ),
        sa.CheckConstraint(
            "weight_kg IS NULL OR weight_kg >= 0",
            name=op.f("ck_users_user_weight_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email_normalized", name=op.f("uq_users_email_normalized")),
        sa.UniqueConstraint("telegram_id", name=op.f("uq_users_telegram_id")),
    )
    op.create_index(op.f("ix_users_email_normalized"), "users", ["email_normalized"])
    op.create_index(op.f("ix_users_phone"), "users", ["phone"])
    op.create_index(op.f("ix_users_status"), "users", ["status"])
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"])

    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_system",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )
    op.create_table(
        "permissions",
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_assigned_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_user_roles_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_role_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "role_id",
            "permission_id",
            name=op.f("pk_role_permissions"),
        ),
    )

    op.create_table(
        "otp_challenges",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("target_email", sa.String(length=320), nullable=False),
        sa.Column("target_email_normalized", sa.String(length=320), nullable=False),
        sa.Column("code_digest", sa.String(length=64), nullable=False),
        sa.Column("code_salt", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_key", sa.String(length=128), nullable=True),
        sa.Column("requested_ip_digest", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name=op.f("ck_otp_challenges_otp_challenge_attempts_valid"),
        ),
        sa.CheckConstraint(
            "length(code_digest) = 64",
            name=op.f("ck_otp_challenges_otp_challenge_digest_length"),
        ),
        sa.CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 10",
            name=op.f("ck_otp_challenges_otp_challenge_max_attempts_valid"),
        ),
        sa.CheckConstraint(
            "purpose IN ('login', 'email_change')",
            name=op.f("ck_otp_challenges_otp_challenge_purpose_valid"),
        ),
        sa.CheckConstraint(
            "length(code_salt) = 32",
            name=op.f("ck_otp_challenges_otp_challenge_salt_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_otp_challenges_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_challenges")),
        sa.UniqueConstraint("active_key", name="uq_otp_challenge_active_key"),
    )
    op.create_index(op.f("ix_otp_challenges_expires_at"), "otp_challenges", ["expires_at"])
    op.create_index(op.f("ix_otp_challenges_purpose"), "otp_challenges", ["purpose"])
    op.create_index(
        op.f("ix_otp_challenges_requested_ip_digest"),
        "otp_challenges",
        ["requested_ip_digest"],
    )
    op.create_index(
        op.f("ix_otp_challenges_target_email_normalized"),
        "otp_challenges",
        ["target_email_normalized"],
    )
    op.create_index(op.f("ix_otp_challenges_user_id"), "otp_challenges", ["user_id"])

    op.create_table(
        "refresh_sessions",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("family_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("generation", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_digest", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "length(token_digest) = 64",
            name=op.f("ck_refresh_sessions_refresh_session_digest_length"),
        ),
        sa.CheckConstraint(
            "generation >= 0",
            name=op.f("ck_refresh_sessions_refresh_session_generation_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["refresh_sessions.id"],
            name=op.f("fk_refresh_sessions_replaced_by_id_refresh_sessions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_sessions")),
        sa.UniqueConstraint("replaced_by_id", name=op.f("uq_refresh_sessions_replaced_by_id")),
        sa.UniqueConstraint("session_id", name=op.f("uq_refresh_sessions_session_id")),
        sa.UniqueConstraint("token_digest", name=op.f("uq_refresh_sessions_token_digest")),
    )
    op.create_index(op.f("ix_refresh_sessions_expires_at"), "refresh_sessions", ["expires_at"])
    op.create_index(op.f("ix_refresh_sessions_family_id"), "refresh_sessions", ["family_id"])
    op.create_index(op.f("ix_refresh_sessions_revoked_at"), "refresh_sessions", ["revoked_at"])
    op.create_index(op.f("ix_refresh_sessions_session_id"), "refresh_sessions", ["session_id"])
    op.create_index(op.f("ix_refresh_sessions_user_id"), "refresh_sessions", ["user_id"])

    op.create_table(
        "security_audit_events",
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("subject_user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("ip_digest", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_security_audit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_user_id"],
            ["users.id"],
            name=op.f("fk_security_audit_events_subject_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_audit_events")),
    )
    op.create_index(
        op.f("ix_security_audit_events_actor_user_id"),
        "security_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        op.f("ix_security_audit_events_created_at"),
        "security_audit_events",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_security_audit_events_event_type"),
        "security_audit_events",
        ["event_type"],
    )
    op.create_index(
        op.f("ix_security_audit_events_session_id"),
        "security_audit_events",
        ["session_id"],
    )
    op.create_index(
        op.f("ix_security_audit_events_subject_user_id"),
        "security_audit_events",
        ["subject_user_id"],
    )

    op.create_table(
        "identity_migration_runs",
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("users_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "length(fingerprint_sha256) = 64",
            name=op.f("ck_identity_migration_runs_identity_run_fingerprint_length"),
        ),
        sa.CheckConstraint(
            "users_count >= 0",
            name=op.f("ck_identity_migration_runs_identity_run_users_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_migration_runs")),
        sa.UniqueConstraint(
            "fingerprint_sha256",
            name=op.f("uq_identity_migration_runs_fingerprint_sha256"),
        ),
    )

    _seed_system_authorization()


def _seed_system_authorization() -> None:
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_system", sa.Boolean),
    )
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("description", sa.Text),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    role_rows = [
        {"id": 1, "name": "customer", "description": "Storefront customer", "is_system": True},
        {"id": 2, "name": "manager", "description": "Operational manager", "is_system": True},
        {"id": 3, "name": "admin", "description": "System administrator", "is_system": True},
    ]
    permission_codes = [
        "profile.read_own",
        "profile.write_own",
        "orders.read_own",
        "catalog.write",
        "orders.read_all",
        "orders.write",
        "crm.access",
        "users.manage",
        "roles.manage",
        "admin.access",
    ]
    permission_rows = [
        {"id": index, "code": code, "description": code}
        for index, code in enumerate(permission_codes, start=1)
    ]
    customer_permission_ids = [1, 2, 3]
    manager_permission_ids = [1, 2, 3, 4, 5, 6, 7, 10]
    admin_permission_ids = list(range(1, len(permission_codes) + 1))

    op.bulk_insert(roles, role_rows)
    op.bulk_insert(permissions, permission_rows)
    op.bulk_insert(
        role_permissions,
        [
            {"role_id": role_id, "permission_id": permission_id}
            for role_id, permission_ids in (
                (1, customer_permission_ids),
                (2, manager_permission_ids),
                (3, admin_permission_ids),
            )
            for permission_id in permission_ids
        ],
    )
    op.execute(
        "SELECT setval(pg_get_serial_sequence('roles', 'id'), (SELECT MAX(id) FROM roles), true)"
    )
    op.execute(
        "SELECT setval(pg_get_serial_sequence('permissions', 'id'), "
        "(SELECT MAX(id) FROM permissions), true)"
    )


def downgrade() -> None:
    op.drop_table("identity_migration_runs")
    op.drop_index(
        op.f("ix_security_audit_events_subject_user_id"), table_name="security_audit_events"
    )
    op.drop_index(op.f("ix_security_audit_events_session_id"), table_name="security_audit_events")
    op.drop_index(op.f("ix_security_audit_events_event_type"), table_name="security_audit_events")
    op.drop_index(op.f("ix_security_audit_events_created_at"), table_name="security_audit_events")
    op.drop_index(
        op.f("ix_security_audit_events_actor_user_id"), table_name="security_audit_events"
    )
    op.drop_table("security_audit_events")
    op.drop_index(op.f("ix_refresh_sessions_user_id"), table_name="refresh_sessions")
    op.drop_index(op.f("ix_refresh_sessions_session_id"), table_name="refresh_sessions")
    op.drop_index(op.f("ix_refresh_sessions_revoked_at"), table_name="refresh_sessions")
    op.drop_index(op.f("ix_refresh_sessions_family_id"), table_name="refresh_sessions")
    op.drop_index(op.f("ix_refresh_sessions_expires_at"), table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
    op.drop_index(op.f("ix_otp_challenges_user_id"), table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_target_email_normalized"), table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_requested_ip_digest"), table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_purpose"), table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_expires_at"), table_name="otp_challenges")
    op.drop_table("otp_challenges")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_index(op.f("ix_users_telegram_id"), table_name="users")
    op.drop_index(op.f("ix_users_status"), table_name="users")
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_email_normalized"), table_name="users")
    op.drop_table("users")
