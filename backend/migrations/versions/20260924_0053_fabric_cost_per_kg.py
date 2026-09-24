"""Store fabric purchase price per kilogram."""

import sqlalchemy as sa
from alembic import op

revision = "20260924_0053"
down_revision = "20260924_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crm_fabrics",
        sa.Column("cost_per_kg", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_crm_fabrics_crm_fabric_cost_per_kg_nonnegative"),
        "crm_fabrics",
        "cost_per_kg IS NULL OR cost_per_kg >= 0",
    )
    op.execute(
        """
        UPDATE crm_fabrics
        SET cost_per_kg = ROUND(
            cost_per_meter * 100000 / (density_gsm * width_cm),
            2
        )
        WHERE cost_per_meter IS NOT NULL
          AND density_gsm IS NOT NULL
          AND density_gsm > 0
          AND width_cm > 0
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_crm_fabrics_crm_fabric_cost_per_kg_nonnegative"),
        "crm_fabrics",
        type_="check",
    )
    op.drop_column("crm_fabrics", "cost_per_kg")
