"""Add dual order approval and searchable pattern codes."""

import sqlalchemy as sa
from alembic import op

revision = "20260921_0047"
down_revision = "20260921_0046"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("crm_garment_patterns", sa.Column("code", sa.String(64), nullable=True))
    op.execute(
        sa.text(
            "UPDATE crm_garment_patterns "
            "SET code = 'PAT-' || LPAD(CAST(id AS VARCHAR), 6, '0') "
            "WHERE code IS NULL"
        )
    )
    op.alter_column("crm_garment_patterns", "code", nullable=False)
    op.create_check_constraint(
        "crm_pattern_code_nonempty",
        "crm_garment_patterns",
        "length(trim(code)) > 0",
    )
    op.create_index(
        op.f("ix_crm_garment_patterns_code"),
        "crm_garment_patterns",
        ["code"],
        unique=True,
    )

    op.add_column(
        "production_bags", sa.Column("tech_approved_by_user_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "production_bags", sa.Column("tech_approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "production_bags", sa.Column("dtf_approved_by_user_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "production_bags", sa.Column("dtf_approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_production_bags_tech_approved_by",
        "production_bags",
        "users",
        ["tech_approved_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_production_bags_dtf_approved_by",
        "production_bags",
        "users",
        ["dtf_approved_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "production_bag_tech_approval_consistent",
        "production_bags",
        "(tech_approved_at IS NULL AND tech_approved_by_user_id IS NULL) OR "
        "(tech_approved_at IS NOT NULL AND tech_approved_by_user_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "production_bag_dtf_approval_consistent",
        "production_bags",
        "(dtf_approved_at IS NULL AND dtf_approved_by_user_id IS NULL) OR "
        "(dtf_approved_at IS NOT NULL AND dtf_approved_by_user_id IS NOT NULL)",
    )


def downgrade():
    op.drop_constraint("production_bag_dtf_approval_consistent", "production_bags", type_="check")
    op.drop_constraint("production_bag_tech_approval_consistent", "production_bags", type_="check")
    op.drop_constraint("fk_production_bags_dtf_approved_by", "production_bags", type_="foreignkey")
    op.drop_constraint("fk_production_bags_tech_approved_by", "production_bags", type_="foreignkey")
    op.drop_column("production_bags", "dtf_approved_at")
    op.drop_column("production_bags", "dtf_approved_by_user_id")
    op.drop_column("production_bags", "tech_approved_at")
    op.drop_column("production_bags", "tech_approved_by_user_id")

    op.drop_index(op.f("ix_crm_garment_patterns_code"), table_name="crm_garment_patterns")
    op.drop_constraint("crm_pattern_code_nonempty", "crm_garment_patterns", type_="check")
    op.drop_column("crm_garment_patterns", "code")
