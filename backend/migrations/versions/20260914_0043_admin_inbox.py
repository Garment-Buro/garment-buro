"""Add admin inbox records and reconcile current production access."""

import sqlalchemy as sa
from alembic import op

revision = "20260914_0043"
down_revision = "20260912_0042"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            """
            INSERT INTO production_employees (user_id, primary_station)
            SELECT DISTINCT ON (credentials.user_id)
                credentials.user_id,
                credentials.station
            FROM production_credentials credentials
            WHERE credentials.active
              AND credentials.station IN (
                  'tech','kit','cut','dtf','workshop','application',
                  'sewing','press','qc','packing','shipping'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM production_demo_employees demo
                  WHERE demo.user_id = credentials.user_id
              )
            ORDER BY credentials.user_id, credentials.updated_at DESC, credentials.id DESC
            ON CONFLICT (user_id) DO NOTHING
            """
        )
    )
    op.create_table(
        "admin_inbox_items",
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="new"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=True),
        sa.Column("reporter_name", sa.String(255), nullable=True),
        sa.Column("reporter_email", sa.String(320), nullable=True),
        sa.Column("reporter_phone", sa.String(64), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("production_unit_id", sa.Integer(), nullable=True),
        sa.Column("station", sa.String(24), nullable=True),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            "kind IN ('support','production_problem')",
            name=op.f("ck_admin_inbox_items_admin_inbox_kind_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('new','in_progress','resolved','closed')",
            name=op.f("ck_admin_inbox_items_admin_inbox_status_valid"),
        ),
        sa.CheckConstraint(
            "priority IN ('low','normal','high','critical')",
            name=op.f("ck_admin_inbox_items_admin_inbox_priority_valid"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_admin_inbox_items_admin_inbox_version_positive"),
        ),
        sa.CheckConstraint(
            "(status IN ('resolved','closed') AND resolved_at IS NOT NULL) OR "
            "(status IN ('new','in_progress') AND resolved_at IS NULL)",
            name=op.f("ck_admin_inbox_items_admin_inbox_resolution_consistent"),
        ),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["crm_order_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["production_unit_id"], ["crm_production_units.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in (
        "kind",
        "status",
        "priority",
        "reporter_user_id",
        "order_id",
        "project_id",
        "production_unit_id",
        "assigned_to_user_id",
    ):
        op.create_index(op.f(f"ix_admin_inbox_items_{column}"), "admin_inbox_items", [column])
    op.create_index(
        "ix_admin_inbox_kind_status_created",
        "admin_inbox_items",
        ["kind", "status", "created_at"],
    )
    op.add_column(
        "production_work_items",
        sa.Column("problem_inbox_item_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_production_work_items_problem_inbox",
        "production_work_items",
        "admin_inbox_items",
        ["problem_inbox_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_production_work_items_problem_inbox_item_id",
        "production_work_items",
        ["problem_inbox_item_id"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO admin_inbox_items (
                kind, status, priority, subject, message,
                order_id, project_id, production_unit_id
            )
            SELECT
                'production_problem', 'new', 'normal',
                'Проблема с изделием №' || CAST(work.unit_id AS VARCHAR),
                work.issue, project.order_id, bag.project_id, work.unit_id
            FROM production_work_items work
            JOIN production_bags bag ON bag.id = work.bag_id
            JOIN crm_order_projects project ON project.id = bag.project_id
            WHERE work.issue IS NOT NULL
              AND work.problem_inbox_item_id IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE production_work_items work
            SET problem_inbox_item_id = (
                SELECT inbox.id
                FROM admin_inbox_items inbox
                WHERE inbox.kind = 'production_problem'
                  AND inbox.production_unit_id = work.unit_id
                ORDER BY inbox.id DESC
                LIMIT 1
            )
            WHERE work.issue IS NOT NULL
              AND work.problem_inbox_item_id IS NULL
            """
        )
    )


def downgrade():
    op.drop_index(
        "ix_production_work_items_problem_inbox_item_id",
        table_name="production_work_items",
    )
    op.drop_constraint(
        "fk_production_work_items_problem_inbox",
        "production_work_items",
        type_="foreignkey",
    )
    op.drop_column("production_work_items", "problem_inbox_item_id")
    op.drop_table("admin_inbox_items")
