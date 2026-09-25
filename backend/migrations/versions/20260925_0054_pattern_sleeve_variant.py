"""Store the sleeve file variant instead of sleeve and height measurements."""

import sqlalchemy as sa
from alembic import op

revision = "20260925_0054"
down_revision = "20260924_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crm_garment_patterns",
        sa.Column(
            "sleeve_variant",
            sa.String(length=16),
            nullable=False,
            server_default="standard",
        ),
    )
    op.execute(
        """
        UPDATE crm_garment_patterns
        SET sleeve_variant = 'height'
        WHERE height_cm IS NOT NULL
        """
    )
    op.create_check_constraint(
        op.f("ck_crm_garment_patterns_crm_pattern_sleeve_variant_valid"),
        "crm_garment_patterns",
        "sleeve_variant IN ('standard', 'height')",
    )
    op.create_index(
        op.f("ix_crm_garment_patterns_sleeve_variant"),
        "crm_garment_patterns",
        ["sleeve_variant"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_crm_garment_patterns_sleeve_variant"),
        table_name="crm_garment_patterns",
    )
    op.drop_constraint(
        op.f("ck_crm_garment_patterns_crm_pattern_sleeve_variant_valid"),
        "crm_garment_patterns",
        type_="check",
    )
    op.drop_column("crm_garment_patterns", "sleeve_variant")
