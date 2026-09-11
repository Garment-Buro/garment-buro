"""Separate production employees from customer identity profiles."""

import sqlalchemy as sa
from alembic import context, op

revision = "20260911_0041"
down_revision = "20260909_0040"
branch_labels = None
depends_on = None

STATIONS_SQL = "'tech','kit','cut','dtf','application','sewing','press','qc','packing','shipping'"


def upgrade():
    op.add_column("users", sa.Column("internal_identity", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_users_internal_identity", "users", ["internal_identity"])
    op.drop_constraint("ck_users_user_identifier_present", "users", type_="check")
    op.create_check_constraint(
        "ck_users_user_identifier_present",
        "users",
        "status = 'deleted' OR email_normalized IS NOT NULL OR telegram_id IS NOT NULL "
        "OR internal_identity IS NOT NULL",
    )
    op.create_table(
        "production_employees",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("primary_station", sa.String(24), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"primary_station IN ({STATIONS_SQL})",
            name="ck_production_employees_production_employee_station_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_production_employees_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_production_employees_created_by_user_id_users",
        ),
        sa.UniqueConstraint("user_id", name="uq_production_employees_user_id"),
    )
    op.create_index("ix_production_employees_user_id", "production_employees", ["user_id"])
    op.execute(
        sa.text(
            f"""
            INSERT INTO production_employees (user_id, primary_station)
            SELECT DISTINCT ON (credentials.user_id)
                credentials.user_id,
                credentials.station
            FROM production_credentials credentials
            WHERE credentials.active
              AND credentials.station IN ({STATIONS_SQL})
              AND NOT EXISTS (
                  SELECT 1 FROM production_demo_employees demo
                  WHERE demo.user_id = credentials.user_id
              )
            ORDER BY credentials.user_id, credentials.updated_at DESC, credentials.id DESC
            ON CONFLICT (user_id) DO NOTHING
            """
        )
    )


def downgrade():
    if not context.is_offline_mode() and op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM users WHERE internal_identity IS NOT NULL "
            "AND email_normalized IS NULL AND telegram_id IS NULL AND status <> 'deleted'"
        )
    ):
        raise RuntimeError("Archive internal production employees before schema downgrade")
    op.drop_index("ix_production_employees_user_id", table_name="production_employees")
    op.drop_table("production_employees")
    op.drop_constraint("ck_users_user_identifier_present", "users", type_="check")
    op.create_check_constraint(
        "ck_users_user_identifier_present",
        "users",
        "status = 'deleted' OR email_normalized IS NOT NULL OR telegram_id IS NOT NULL",
    )
    op.drop_constraint("uq_users_internal_identity", "users", type_="unique")
    op.drop_column("users", "internal_identity")
