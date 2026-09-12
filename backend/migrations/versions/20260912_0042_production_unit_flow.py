"""Per-piece production handoffs, shared workshop and unguessable bag labels."""

import sqlalchemy as sa
from alembic import context, op

revision = "20260912_0042"
down_revision = "20260911_0041"
branch_labels = None
depends_on = None

OLD_STATIONS = "'tech','kit','cut','dtf','application','sewing','press','qc','packing','shipping'"


def upgrade():
    op.execute(
        sa.text(
            "INSERT INTO permissions (code, description) VALUES ('production.workshop', 'Shared workshop') ON CONFLICT (code) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO roles (name, description, is_system) VALUES ('production_workshop', 'Shared workshop', true) ON CONFLICT (name) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) SELECT r.id, p.id FROM roles r CROSS JOIN permissions p WHERE (r.name = 'production_workshop' AND p.code IN ('production.access','production.workshop','profile.read_own','profile.write_own')) OR (r.name = 'production_admin' AND p.code = 'payments.manage') OR (r.name = 'admin' AND p.code = 'production.workshop') ON CONFLICT DO NOTHING"
        )
    )
    # Existing physical bags keep their original routing until completion.
    op.add_column(
        "production_bags",
        sa.Column("flow_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("production_bags", "flow_version", server_default="2")
    for table in ("production_bags", "production_work_items"):
        op.add_column(table, sa.Column("public_token", sa.String(64), nullable=True))
        op.create_unique_constraint(f"uq_{table}_public_token", table, ["public_token"])
    op.add_column("production_work_items", sa.Column("lane", sa.String(24), nullable=True))
    op.create_index("ix_production_work_items_lane", "production_work_items", ["lane"])
    op.add_column(
        "production_work_items", sa.Column("dtf_due_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "production_employees",
        sa.Column("availability", sa.String(24), nullable=False, server_default="available"),
    )
    op.drop_constraint(
        op.f("ck_production_employees_production_employee_station_valid"),
        "production_employees",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_production_employees_production_employee_station_valid"),
        "production_employees",
        f"primary_station IN ({OLD_STATIONS},'workshop')",
    )
    op.create_check_constraint(
        op.f("ck_production_bags_production_flow_version_valid"),
        "production_bags",
        "flow_version IN (1,2)",
    )
    op.create_check_constraint(
        op.f("ck_production_work_items_production_lane_valid"),
        "production_work_items",
        "lane IS NULL OR lane IN ('cut','kit','waiting_dtf','workshop','packing','done')",
    )
    op.create_check_constraint(
        op.f("ck_production_employees_production_availability_valid"),
        "production_employees",
        "availability IN ('available','sick','vacation','absent')",
    )


def downgrade():
    if not context.is_offline_mode() and op.get_bind().scalar(
        sa.text("SELECT count(*) FROM production_bags WHERE flow_version = 2")
    ):
        raise RuntimeError(
            "New production bags exist; keep the schema and roll back application only"
        )
    op.drop_constraint(
        op.f("ck_production_bags_production_flow_version_valid"), "production_bags", type_="check"
    )
    op.drop_constraint(
        op.f("ck_production_work_items_production_lane_valid"),
        "production_work_items",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_production_employees_production_availability_valid"),
        "production_employees",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_production_employees_production_employee_station_valid"),
        "production_employees",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_production_employees_production_employee_station_valid"),
        "production_employees",
        f"primary_station IN ({OLD_STATIONS})",
    )
    op.drop_column("production_employees", "availability")
    op.drop_column("production_work_items", "dtf_due_at")
    op.drop_index("ix_production_work_items_lane", table_name="production_work_items")
    op.drop_column("production_work_items", "lane")
    for table in ("production_work_items", "production_bags"):
        op.drop_constraint(f"uq_{table}_public_token", table, type_="unique")
        op.drop_column(table, "public_token")
    op.drop_column("production_bags", "flow_version")
