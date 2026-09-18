"""Complete the product assortment, pattern and warehouse reference foundation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0044"
down_revision: str | Sequence[str] | None = "20260914_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("slug", sa.String(96), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), primary_key=True),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(slug)) > 0",
            name=op.f("ck_product_categories_product_category_slug_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_product_categories_product_category_name_nonempty"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_product_categories_product_category_version_positive"),
        ),
    )
    op.create_index(
        op.f("ix_product_categories_slug"),
        "product_categories",
        ["slug"],
        unique=True,
    )
    for column in ("name", "is_active"):
        op.create_index(
            op.f(f"ix_product_categories_{column}"),
            "product_categories",
            [column],
        )
    op.add_column("products", sa.Column("category_id", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("garment_model_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_products_category_id_product_categories"),
        "products",
        "product_categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_products_garment_model_id_crm_garment_models"),
        "products",
        "crm_garment_models",
        ["garment_model_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_products_category_id"), "products", ["category_id"])
    op.create_index(op.f("ix_products_garment_model_id"), "products", ["garment_model_id"])
    op.execute(
        sa.text(
            "UPDATE products SET garment_model_id = ("
            "SELECT links.garment_model_id FROM crm_catalog_product_model_links links "
            "WHERE links.catalog_product_id = products.id ORDER BY links.id LIMIT 1"
            ") WHERE garment_model_id IS NULL"
        )
    )
    op.drop_table("crm_catalog_product_model_links")
    op.add_column("product_variants", sa.Column("garment_size_id", sa.Integer(), nullable=True))
    op.add_column("product_variants", sa.Column("fabric_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_product_variants_garment_size_id_crm_garment_sizes"),
        "product_variants",
        "crm_garment_sizes",
        ["garment_size_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_product_variants_fabric_id_crm_fabrics"),
        "product_variants",
        "crm_fabrics",
        ["fabric_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_product_variants_garment_size_id"),
        "product_variants",
        ["garment_size_id"],
    )
    op.create_index(op.f("ix_product_variants_fabric_id"), "product_variants", ["fabric_id"])

    op.add_column(
        "crm_fabrics",
        sa.Column(
            "minimum_stock_meters",
            sa.Numeric(14, 3),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        op.f("ck_crm_fabrics_crm_fabric_minimum_stock_nonnegative"),
        "crm_fabrics",
        "minimum_stock_meters >= 0",
    )
    op.add_column(
        "crm_garment_models",
        sa.Column("size_chart_media_object_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_crm_garment_models_size_chart_media_object_id_media_objects"),
        "crm_garment_models",
        "media_objects",
        ["size_chart_media_object_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_crm_garment_models_size_chart_media_object_id"),
        "crm_garment_models",
        ["size_chart_media_object_id"],
    )
    op.add_column(
        "crm_garment_sizes",
        sa.Column("min_sleeve_length_cm", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "crm_garment_sizes",
        sa.Column("max_sleeve_length_cm", sa.Numeric(10, 2), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_crm_garment_sizes_crm_garment_size_min_sleeve_positive"),
        "crm_garment_sizes",
        "min_sleeve_length_cm IS NULL OR min_sleeve_length_cm > 0",
    )
    op.create_check_constraint(
        op.f("ck_crm_garment_sizes_crm_garment_size_max_sleeve_positive"),
        "crm_garment_sizes",
        "max_sleeve_length_cm IS NULL OR max_sleeve_length_cm > 0",
    )
    op.create_check_constraint(
        op.f("ck_crm_garment_sizes_crm_garment_size_sleeve_range_valid"),
        "crm_garment_sizes",
        "min_sleeve_length_cm IS NULL OR max_sleeve_length_cm IS NULL "
        "OR min_sleeve_length_cm <= max_sleeve_length_cm",
    )
    op.add_column(
        "crm_tech_card_checkpoints",
        sa.Column("role_code", sa.String(64), nullable=True),
    )
    op.execute(sa.text("UPDATE crm_tech_card_checkpoints SET role_code = stage_code"))
    op.alter_column("crm_tech_card_checkpoints", "role_code", nullable=False)
    op.create_check_constraint(
        op.f("ck_crm_tech_card_checkpoints_crm_tech_card_checkpoint_role_nonempty"),
        "crm_tech_card_checkpoints",
        "length(trim(role_code)) > 0",
    )
    op.create_index(
        op.f("ix_crm_tech_card_checkpoints_role_code"),
        "crm_tech_card_checkpoints",
        ["role_code"],
    )

    op.create_table(
        "crm_garment_patterns",
        sa.Column("garment_model_id", sa.Integer(), nullable=False),
        sa.Column("garment_size_id", sa.Integer(), nullable=False),
        sa.Column("media_object_id", sa.Integer(), nullable=False),
        sa.Column("grid_key", sa.String(160), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("width_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("length_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("sleeve_length_cm", sa.Numeric(10, 2), nullable=True),
        sa.Column("height_cm", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), primary_key=True),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(grid_key)) > 0",
            name=op.f("ck_crm_garment_patterns_crm_pattern_grid_key_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_crm_garment_patterns_crm_pattern_name_nonempty"),
        ),
        sa.CheckConstraint(
            "width_cm > 0",
            name=op.f("ck_crm_garment_patterns_crm_pattern_width_positive"),
        ),
        sa.CheckConstraint(
            "length_cm > 0",
            name=op.f("ck_crm_garment_patterns_crm_pattern_length_positive"),
        ),
        sa.CheckConstraint(
            "sleeve_length_cm IS NULL OR sleeve_length_cm > 0",
            name=op.f("ck_crm_garment_patterns_crm_pattern_sleeve_positive"),
        ),
        sa.CheckConstraint(
            "height_cm IS NULL OR height_cm > 0",
            name=op.f("ck_crm_garment_patterns_crm_pattern_height_positive"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_garment_patterns_crm_pattern_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["garment_model_id"], ["crm_garment_models.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["garment_size_id"], ["crm_garment_sizes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["media_object_id"], ["media_objects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "garment_model_id",
            "grid_key",
            name="uq_crm_garment_pattern_model_grid",
        ),
    )
    for column in ("garment_model_id", "garment_size_id", "media_object_id", "is_active"):
        op.create_index(
            op.f(f"ix_crm_garment_patterns_{column}"),
            "crm_garment_patterns",
            [column],
        )

    op.create_table(
        "crm_garment_fabric_requirements",
        sa.Column("garment_model_id", sa.Integer(), nullable=False),
        sa.Column("fabric_id", sa.Integer(), nullable=False),
        sa.Column("meters_per_unit", sa.Numeric(12, 3), nullable=False),
        sa.Column("waste_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), primary_key=True),
        *_timestamps(),
        sa.CheckConstraint(
            "meters_per_unit > 0",
            name=op.f("ck_crm_garment_fabric_requirements_crm_garment_fabric_meters_positive"),
        ),
        sa.CheckConstraint(
            "waste_percent >= 0 AND waste_percent <= 100",
            name=op.f("ck_crm_garment_fabric_requirements_crm_garment_fabric_waste_valid"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_garment_fabric_requirements_crm_garment_fabric_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["garment_model_id"], ["crm_garment_models.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["fabric_id"], ["crm_fabrics.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "garment_model_id",
            "fabric_id",
            name="uq_crm_garment_fabric_requirement",
        ),
    )
    for column in ("garment_model_id", "fabric_id"):
        op.create_index(
            op.f(f"ix_crm_garment_fabric_requirements_{column}"),
            "crm_garment_fabric_requirements",
            [column],
        )

    op.create_table(
        "crm_accessory_categories",
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), primary_key=True),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name=op.f("ck_crm_accessory_categories_crm_accessory_category_code_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_crm_accessory_categories_crm_accessory_category_name_nonempty"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_accessory_categories_crm_accessory_category_version_positive"),
        ),
    )
    op.create_index(
        op.f("ix_crm_accessory_categories_code"),
        "crm_accessory_categories",
        ["code"],
        unique=True,
    )
    for column in ("name", "is_active"):
        op.create_index(
            op.f(f"ix_crm_accessory_categories_{column}"),
            "crm_accessory_categories",
            [column],
        )

    op.create_table(
        "crm_accessories",
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minimum_stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("photo_media_object_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), primary_key=True),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name=op.f("ck_crm_accessories_crm_accessory_code_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_crm_accessories_crm_accessory_name_nonempty"),
        ),
        sa.CheckConstraint(
            "unit_cost >= 0", name=op.f("ck_crm_accessories_crm_accessory_cost_nonnegative")
        ),
        sa.CheckConstraint(
            "currency = 'RUB'", name=op.f("ck_crm_accessories_crm_accessory_currency_rub")
        ),
        sa.CheckConstraint(
            "stock_quantity >= 0",
            name=op.f("ck_crm_accessories_crm_accessory_stock_nonnegative"),
        ),
        sa.CheckConstraint(
            "minimum_stock_quantity >= 0",
            name=op.f("ck_crm_accessories_crm_accessory_minimum_stock_nonnegative"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_crm_accessories_crm_accessory_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["crm_accessory_categories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["photo_media_object_id"], ["media_objects.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(op.f("ix_crm_accessories_code"), "crm_accessories", ["code"], unique=True)
    for column in ("category_id", "name", "photo_media_object_id", "is_active"):
        op.create_index(op.f(f"ix_crm_accessories_{column}"), "crm_accessories", [column])

    op.create_table(
        "crm_garment_accessory_requirements",
        sa.Column("garment_model_id", sa.Integer(), nullable=False),
        sa.Column("accessory_id", sa.Integer(), nullable=False),
        sa.Column("quantity_per_unit", sa.Numeric(12, 3), nullable=False),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), primary_key=True),
        *_timestamps(),
        sa.CheckConstraint(
            "quantity_per_unit > 0",
            name=op.f(
                "ck_crm_garment_accessory_requirements_crm_garment_accessory_quantity_positive"
            ),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f(
                "ck_crm_garment_accessory_requirements_crm_garment_accessory_version_positive"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["garment_model_id"], ["crm_garment_models.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["accessory_id"], ["crm_accessories.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "garment_model_id",
            "accessory_id",
            name="uq_crm_garment_accessory_requirement",
        ),
    )
    for column in ("garment_model_id", "accessory_id"):
        op.create_index(
            op.f(f"ix_crm_garment_accessory_requirements_{column}"),
            "crm_garment_accessory_requirements",
            [column],
        )

    op.create_table(
        "crm_packaging_boxes",
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("inner_length_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("inner_width_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("inner_height_cm", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_items", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minimum_stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("photo_media_object_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), primary_key=True),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name=op.f("ck_crm_packaging_boxes_crm_box_code_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_crm_packaging_boxes_crm_box_name_nonempty"),
        ),
        sa.CheckConstraint(
            "inner_length_cm > 0",
            name=op.f("ck_crm_packaging_boxes_crm_box_length_positive"),
        ),
        sa.CheckConstraint(
            "inner_width_cm > 0",
            name=op.f("ck_crm_packaging_boxes_crm_box_width_positive"),
        ),
        sa.CheckConstraint(
            "inner_height_cm > 0",
            name=op.f("ck_crm_packaging_boxes_crm_box_height_positive"),
        ),
        sa.CheckConstraint(
            "max_items > 0", name=op.f("ck_crm_packaging_boxes_crm_box_max_items_positive")
        ),
        sa.CheckConstraint(
            "unit_cost >= 0", name=op.f("ck_crm_packaging_boxes_crm_box_cost_nonnegative")
        ),
        sa.CheckConstraint(
            "currency = 'RUB'", name=op.f("ck_crm_packaging_boxes_crm_box_currency_rub")
        ),
        sa.CheckConstraint(
            "stock_quantity >= 0",
            name=op.f("ck_crm_packaging_boxes_crm_box_stock_nonnegative"),
        ),
        sa.CheckConstraint(
            "minimum_stock_quantity >= 0",
            name=op.f("ck_crm_packaging_boxes_crm_box_minimum_stock_nonnegative"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_crm_packaging_boxes_crm_box_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["photo_media_object_id"], ["media_objects.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        op.f("ix_crm_packaging_boxes_code"),
        "crm_packaging_boxes",
        ["code"],
        unique=True,
    )
    for column in ("name", "photo_media_object_id", "is_active"):
        op.create_index(op.f(f"ix_crm_packaging_boxes_{column}"), "crm_packaging_boxes", [column])

    op.create_table(
        "crm_garment_packaging_rules",
        sa.Column("garment_model_id", sa.Integer(), nullable=False),
        sa.Column("box_id", sa.Integer(), nullable=False),
        sa.Column("max_items", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), primary_key=True),
        *_timestamps(),
        sa.CheckConstraint(
            "max_items > 0",
            name=op.f("ck_crm_garment_packaging_rules_crm_garment_packaging_max_items_positive"),
        ),
        sa.CheckConstraint(
            "priority >= 0",
            name=op.f("ck_crm_garment_packaging_rules_crm_garment_packaging_priority_nonnegative"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_garment_packaging_rules_crm_garment_packaging_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["garment_model_id"], ["crm_garment_models.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["box_id"], ["crm_packaging_boxes.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "garment_model_id",
            "box_id",
            name="uq_crm_garment_packaging_rule",
        ),
    )
    for column in ("garment_model_id", "box_id"):
        op.create_index(
            op.f(f"ix_crm_garment_packaging_rules_{column}"),
            "crm_garment_packaging_rules",
            [column],
        )


def downgrade() -> None:
    op.drop_table("crm_garment_packaging_rules")
    op.drop_table("crm_packaging_boxes")
    op.drop_table("crm_garment_accessory_requirements")
    op.drop_table("crm_accessories")
    op.drop_table("crm_accessory_categories")
    op.drop_table("crm_garment_fabric_requirements")
    op.drop_table("crm_garment_patterns")

    op.drop_index(op.f("ix_product_variants_fabric_id"), table_name="product_variants")
    op.drop_index(op.f("ix_product_variants_garment_size_id"), table_name="product_variants")
    op.drop_constraint(
        op.f("fk_product_variants_fabric_id_crm_fabrics"),
        "product_variants",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_product_variants_garment_size_id_crm_garment_sizes"),
        "product_variants",
        type_="foreignkey",
    )
    op.drop_column("product_variants", "fabric_id")
    op.drop_column("product_variants", "garment_size_id")

    op.create_table(
        "crm_catalog_product_model_links",
        sa.Column("garment_model_id", sa.Integer(), nullable=False),
        sa.Column("catalog_product_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.ForeignKeyConstraint(
            ["garment_model_id"], ["crm_garment_models.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["catalog_product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "catalog_product_id",
            name="uq_crm_catalog_product_model_link_product",
        ),
    )
    for column in ("garment_model_id", "catalog_product_id", "created_by_user_id"):
        op.create_index(
            op.f(f"ix_crm_catalog_product_model_links_{column}"),
            "crm_catalog_product_model_links",
            [column],
        )
    op.execute(
        sa.text(
            "INSERT INTO crm_catalog_product_model_links "
            "(garment_model_id, catalog_product_id, created_by_user_id, created_at) "
            "SELECT garment_model_id, id, NULL, now() FROM products "
            "WHERE garment_model_id IS NOT NULL"
        )
    )

    op.drop_index(op.f("ix_products_garment_model_id"), table_name="products")
    op.drop_index(op.f("ix_products_category_id"), table_name="products")
    op.drop_constraint(
        op.f("fk_products_garment_model_id_crm_garment_models"),
        "products",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_products_category_id_product_categories"),
        "products",
        type_="foreignkey",
    )
    op.drop_column("products", "garment_model_id")
    op.drop_column("products", "category_id")
    op.drop_table("product_categories")

    op.drop_index(
        op.f("ix_crm_tech_card_checkpoints_role_code"),
        table_name="crm_tech_card_checkpoints",
    )
    op.drop_constraint(
        op.f("ck_crm_tech_card_checkpoints_crm_tech_card_checkpoint_role_nonempty"),
        "crm_tech_card_checkpoints",
        type_="check",
    )
    op.drop_column("crm_tech_card_checkpoints", "role_code")
    for constraint in (
        "crm_garment_size_sleeve_range_valid",
        "crm_garment_size_max_sleeve_positive",
        "crm_garment_size_min_sleeve_positive",
    ):
        op.drop_constraint(
            op.f(f"ck_crm_garment_sizes_{constraint}"),
            "crm_garment_sizes",
            type_="check",
        )
    op.drop_column("crm_garment_sizes", "max_sleeve_length_cm")
    op.drop_column("crm_garment_sizes", "min_sleeve_length_cm")
    op.drop_index(
        op.f("ix_crm_garment_models_size_chart_media_object_id"),
        table_name="crm_garment_models",
    )
    op.drop_constraint(
        op.f("fk_crm_garment_models_size_chart_media_object_id_media_objects"),
        "crm_garment_models",
        type_="foreignkey",
    )
    op.drop_column("crm_garment_models", "size_chart_media_object_id")
    op.drop_constraint(
        op.f("ck_crm_fabrics_crm_fabric_minimum_stock_nonnegative"),
        "crm_fabrics",
        type_="check",
    )
    op.drop_column("crm_fabrics", "minimum_stock_meters")
