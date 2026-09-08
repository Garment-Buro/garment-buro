"""Personal production codes and isolated floor sessions."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0036"
down_revision = "20260908_0035"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "production_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("station", sa.String(24), nullable=False),
        sa.Column("code_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_production_credentials_user_id", "production_credentials", ["user_id"])
    op.create_table(
        "production_sessions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column(
            "credential_id",
            sa.Integer(),
            sa.ForeignKey("production_credentials.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_production_sessions_credential_id", "production_sessions", ["credential_id"]
    )
    op.create_index("ix_production_sessions_expires_at", "production_sessions", ["expires_at"])
    op.create_table(
        "production_login_limits",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_production_login_limits_expires_at", "production_login_limits", ["expires_at"]
    )


def downgrade():
    op.drop_table("production_sessions")
    op.drop_table("production_login_limits")
    op.drop_table("production_credentials")
