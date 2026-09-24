"""Store base garment dimensions per size."""

import sqlalchemy as sa
from alembic import op

revision = "20260924_0052"
down_revision = "20260924_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crm_garment_sizes",
        sa.Column("base_length_cm", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "crm_garment_sizes",
        sa.Column("base_width_cm", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_crm_garment_sizes_crm_garment_size_base_length_positive"),
        "crm_garment_sizes",
        "base_length_cm IS NULL OR base_length_cm > 0",
    )
    op.create_check_constraint(
        op.f("ck_crm_garment_sizes_crm_garment_size_base_width_positive"),
        "crm_garment_sizes",
        "base_width_cm IS NULL OR base_width_cm > 0",
    )
    op.execute(
        """
        UPDATE crm_garment_sizes
        SET base_length_cm = (
            SELECT crm_garment_models.base_length_cm
            FROM crm_garment_models
            WHERE crm_garment_models.id = crm_garment_sizes.garment_model_id
        )
        WHERE base_length_cm IS NULL
        """
    )
    op.execute(
        """
        UPDATE crm_garment_sizes
        SET base_width_cm = (
            SELECT crm_garment_models.base_width_cm
            FROM crm_garment_models
            WHERE crm_garment_models.id = crm_garment_sizes.garment_model_id
        )
        WHERE base_width_cm IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_crm_garment_sizes_crm_garment_size_base_width_positive"),
        "crm_garment_sizes",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_crm_garment_sizes_crm_garment_size_base_length_positive"),
        "crm_garment_sizes",
        type_="check",
    )
    op.drop_column("crm_garment_sizes", "base_width_cm")
    op.drop_column("crm_garment_sizes", "base_length_cm")
