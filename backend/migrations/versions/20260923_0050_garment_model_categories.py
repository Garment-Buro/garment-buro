"""Add garment model categories."""

import sqlalchemy as sa
from alembic import op

revision = "20260923_0050"
down_revision = "20260923_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_garment_model_categories",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name=op.f("ck_crm_garment_model_categories_crm_garment_model_category_code_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_crm_garment_model_categories_crm_garment_model_category_name_nonempty"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f(
                "ck_crm_garment_model_categories_crm_garment_model_category_version_positive"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_garment_model_categories")),
    )
    op.create_index(
        op.f("ix_crm_garment_model_categories_code"),
        "crm_garment_model_categories",
        ["code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_crm_garment_model_categories_is_active"),
        "crm_garment_model_categories",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_garment_model_categories_name"),
        "crm_garment_model_categories",
        ["name"],
        unique=True,
    )
    op.bulk_insert(
        sa.table(
            "crm_garment_model_categories",
            sa.column("code", sa.String()),
            sa.column("name", sa.String()),
            sa.column("is_active", sa.Boolean()),
            sa.column("version", sa.Integer()),
        ),
        [
            {"code": "TSHIRT", "name": "Майка", "is_active": True, "version": 1},
            {"code": "HOODIE", "name": "Худи", "is_active": True, "version": 1},
            {"code": "PANTS", "name": "Штаны", "is_active": True, "version": 1},
        ],
    )
    op.add_column(
        "crm_garment_models",
        sa.Column("category_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_crm_garment_models_category_id"),
        "crm_garment_models",
        ["category_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_crm_garment_models_category_id_crm_garment_model_categories"),
        "crm_garment_models",
        "crm_garment_model_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_crm_garment_models_category_id_crm_garment_model_categories"),
        "crm_garment_models",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_crm_garment_models_category_id"), table_name="crm_garment_models")
    op.drop_column("crm_garment_models", "category_id")
    op.drop_index(
        op.f("ix_crm_garment_model_categories_name"),
        table_name="crm_garment_model_categories",
    )
    op.drop_index(
        op.f("ix_crm_garment_model_categories_is_active"),
        table_name="crm_garment_model_categories",
    )
    op.drop_index(
        op.f("ix_crm_garment_model_categories_code"),
        table_name="crm_garment_model_categories",
    )
    op.drop_table("crm_garment_model_categories")
