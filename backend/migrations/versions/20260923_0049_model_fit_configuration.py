"""Store model fit configuration and sleeve choices."""

import sqlalchemy as sa
from alembic import op

revision = "20260923_0049"
down_revision = "20260921_0048"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("uq_product_variant_identity", "product_variants", type_="unique")
    op.create_unique_constraint(
        "uq_product_variant_selection",
        "product_variants",
        ["product_id", "garment_size_id", "fabric_id"],
    )
    op.add_column("crm_garment_models", sa.Column("base_size_code", sa.String(32)))
    op.add_column("crm_garment_models", sa.Column("fit_model_name", sa.String(120)))
    op.add_column(
        "crm_garment_models",
        sa.Column("fit_model_height_cm", sa.Numeric(10, 2)),
    )
    op.create_check_constraint(
        "crm_garment_model_fit_height_positive",
        "crm_garment_models",
        "fit_model_height_cm IS NULL OR fit_model_height_cm > 0",
    )
    op.add_column(
        "crm_garment_sizes",
        sa.Column(
            "allow_standard_sleeve",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "crm_garment_sizes",
        sa.Column(
            "allow_height_sleeve",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_check_constraint(
        "crm_garment_size_sleeve_option_required",
        "crm_garment_sizes",
        "allow_standard_sleeve OR allow_height_sleeve",
    )
    op.execute(
        sa.text(
            "UPDATE crm_garment_models "
            "SET base_size_code = ("
            "SELECT code FROM crm_garment_sizes "
            "WHERE garment_model_id = crm_garment_models.id AND is_active = true "
            "ORDER BY sort_order, id LIMIT 1"
            ") WHERE base_size_code IS NULL"
        )
    )


def downgrade():
    op.drop_constraint("uq_product_variant_selection", "product_variants", type_="unique")
    op.create_unique_constraint(
        "uq_product_variant_identity",
        "product_variants",
        ["product_id", "size", "color"],
    )
    op.drop_constraint(
        "crm_garment_size_sleeve_option_required",
        "crm_garment_sizes",
        type_="check",
    )
    op.drop_column("crm_garment_sizes", "allow_height_sleeve")
    op.drop_column("crm_garment_sizes", "allow_standard_sleeve")
    op.drop_constraint(
        "crm_garment_model_fit_height_positive",
        "crm_garment_models",
        type_="check",
    )
    op.drop_column("crm_garment_models", "fit_model_height_cm")
    op.drop_column("crm_garment_models", "fit_model_name")
    op.drop_column("crm_garment_models", "base_size_code")
