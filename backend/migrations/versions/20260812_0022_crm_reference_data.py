"""Add versioned CRM fabrics, garment models, sizes, and tech cards.

Revision ID: 20260812_0022
Revises: 20260812_0021
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0022"
down_revision: str | Sequence[str] | None = "20260812_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "crm_fabrics",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("material_type", sa.String(length=100), nullable=True),
        sa.Column("color_name", sa.String(length=64), nullable=False),
        sa.Column("color_hex", sa.String(length=7), nullable=True),
        sa.Column("density_gsm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("width_cm", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("cost_per_meter", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="RUB", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name=op.f("ck_crm_fabrics_crm_fabric_code_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_crm_fabrics_crm_fabric_name_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(color_name)) > 0",
            name=op.f("ck_crm_fabrics_crm_fabric_color_nonempty"),
        ),
        sa.CheckConstraint(
            "density_gsm IS NULL OR density_gsm > 0",
            name=op.f("ck_crm_fabrics_crm_fabric_density_positive"),
        ),
        sa.CheckConstraint(
            "width_cm > 0",
            name=op.f("ck_crm_fabrics_crm_fabric_width_positive"),
        ),
        sa.CheckConstraint(
            "cost_per_meter IS NULL OR cost_per_meter >= 0",
            name=op.f("ck_crm_fabrics_crm_fabric_cost_nonnegative"),
        ),
        sa.CheckConstraint(
            "currency = 'RUB'",
            name=op.f("ck_crm_fabrics_crm_fabric_currency_rub"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_fabrics_crm_fabric_version_positive"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_fabrics")),
    )
    for column in ("color_name", "is_active", "material_type", "name"):
        op.create_index(op.f(f"ix_crm_fabrics_{column}"), "crm_fabrics", [column])
    op.create_index(op.f("ix_crm_fabrics_code"), "crm_fabrics", ["code"], unique=True)

    op.create_table(
        "crm_garment_models",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_height_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("base_length_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("base_width_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("base_weight_g", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name=op.f("ck_crm_garment_models_crm_garment_model_code_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_crm_garment_models_crm_garment_model_name_nonempty"),
        ),
        sa.CheckConstraint(
            "base_height_cm IS NULL OR base_height_cm > 0",
            name=op.f("ck_crm_garment_models_crm_garment_model_height_positive"),
        ),
        sa.CheckConstraint(
            "base_length_cm IS NULL OR base_length_cm > 0",
            name=op.f("ck_crm_garment_models_crm_garment_model_length_positive"),
        ),
        sa.CheckConstraint(
            "base_width_cm IS NULL OR base_width_cm > 0",
            name=op.f("ck_crm_garment_models_crm_garment_model_width_positive"),
        ),
        sa.CheckConstraint(
            "base_weight_g IS NULL OR base_weight_g > 0",
            name=op.f("ck_crm_garment_models_crm_garment_model_weight_positive"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_garment_models_crm_garment_model_version_positive"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_garment_models")),
    )
    op.create_index(
        op.f("ix_crm_garment_models_code"),
        "crm_garment_models",
        ["code"],
        unique=True,
    )
    for column in ("is_active", "name"):
        op.create_index(
            op.f(f"ix_crm_garment_models_{column}"),
            "crm_garment_models",
            [column],
        )

    op.create_table(
        "crm_garment_sizes",
        sa.Column("garment_model_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "base_price", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
        sa.Column("min_height_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("max_height_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("min_length_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("max_length_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("min_width_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("max_width_cm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("extra_width_price_per_cm", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="RUB", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_code_nonempty"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_sort_nonnegative"),
        ),
        sa.CheckConstraint(
            "base_price >= 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "min_height_cm IS NULL OR min_height_cm > 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_min_height_positive"),
        ),
        sa.CheckConstraint(
            "max_height_cm IS NULL OR max_height_cm > 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_max_height_positive"),
        ),
        sa.CheckConstraint(
            "min_height_cm IS NULL OR max_height_cm IS NULL OR min_height_cm <= max_height_cm",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_height_range_valid"),
        ),
        sa.CheckConstraint(
            "min_length_cm IS NULL OR min_length_cm > 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_min_length_positive"),
        ),
        sa.CheckConstraint(
            "max_length_cm IS NULL OR max_length_cm > 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_max_length_positive"),
        ),
        sa.CheckConstraint(
            "min_length_cm IS NULL OR max_length_cm IS NULL OR min_length_cm <= max_length_cm",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_length_range_valid"),
        ),
        sa.CheckConstraint(
            "min_width_cm IS NULL OR min_width_cm > 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_min_width_positive"),
        ),
        sa.CheckConstraint(
            "max_width_cm IS NULL OR max_width_cm > 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_max_width_positive"),
        ),
        sa.CheckConstraint(
            "min_width_cm IS NULL OR max_width_cm IS NULL OR min_width_cm <= max_width_cm",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_width_range_valid"),
        ),
        sa.CheckConstraint(
            "extra_width_price_per_cm IS NULL OR extra_width_price_per_cm >= 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_extra_width_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "currency = 'RUB'",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_currency_rub"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_garment_sizes_crm_garment_size_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["garment_model_id"],
            ["crm_garment_models.id"],
            name=op.f("fk_crm_garment_sizes_garment_model_id_crm_garment_models"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_garment_sizes")),
        sa.UniqueConstraint("garment_model_id", "code", name="uq_crm_garment_size_code"),
    )
    for column in ("code", "garment_model_id", "is_active"):
        op.create_index(
            op.f(f"ix_crm_garment_sizes_{column}"),
            "crm_garment_sizes",
            [column],
        )
    op.create_index(
        "ix_crm_garment_sizes_model_active_sort",
        "crm_garment_sizes",
        ["garment_model_id", "is_active", "sort_order"],
    )

    op.create_table(
        "crm_catalog_product_model_links",
        sa.Column("garment_model_id", sa.Integer(), nullable=False),
        sa.Column("catalog_product_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_product_id"],
            ["products.id"],
            name=op.f("fk_crm_catalog_product_model_links_catalog_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_crm_catalog_product_model_links_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["garment_model_id"],
            ["crm_garment_models.id"],
            name=op.f("fk_crm_catalog_product_model_links_garment_model_id_crm_garment_models"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_catalog_product_model_links")),
        sa.UniqueConstraint(
            "catalog_product_id",
            name="uq_crm_catalog_product_model_link_product",
        ),
    )
    for column in ("catalog_product_id", "created_by_user_id", "garment_model_id"):
        op.create_index(
            op.f(f"ix_crm_catalog_product_model_links_{column}"),
            "crm_catalog_product_model_links",
            [column],
        )

    op.create_table(
        "crm_tech_cards",
        sa.Column("garment_model_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("latest_revision_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name=op.f("ck_crm_tech_cards_crm_tech_card_code_nonempty"),
        ),
        sa.CheckConstraint(
            "latest_revision_number > 0",
            name=op.f("ck_crm_tech_cards_crm_tech_card_latest_revision_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["garment_model_id"],
            ["crm_garment_models.id"],
            name=op.f("fk_crm_tech_cards_garment_model_id_crm_garment_models"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_tech_cards")),
    )
    op.create_index(op.f("ix_crm_tech_cards_code"), "crm_tech_cards", ["code"], unique=True)
    op.create_index(
        op.f("ix_crm_tech_cards_garment_model_id"),
        "crm_tech_cards",
        ["garment_model_id"],
        unique=True,
    )
    op.create_index(op.f("ix_crm_tech_cards_is_active"), "crm_tech_cards", ["is_active"])

    op.create_table(
        "crm_tech_card_revisions",
        sa.Column("tech_card_id", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("based_on_revision_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("description_snapshot", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("published_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "revision_number > 0",
            name=op.f("ck_crm_tech_card_revisions_crm_tech_card_revision_number_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived', 'discarded')",
            name=op.f("ck_crm_tech_card_revisions_crm_tech_card_revision_status_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(name_snapshot)) > 0",
            name=op.f("ck_crm_tech_card_revisions_crm_tech_card_revision_name_nonempty"),
        ),
        sa.CheckConstraint(
            "(status IN ('draft', 'discarded') AND published_at IS NULL "
            "AND published_by_user_id IS NULL) OR "
            "(status IN ('published', 'archived') AND published_at IS NOT NULL "
            "AND published_by_user_id IS NOT NULL)",
            name=op.f("ck_crm_tech_card_revisions_crm_tech_card_revision_publication_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["tech_card_id", "based_on_revision_id"],
            ["crm_tech_card_revisions.tech_card_id", "crm_tech_card_revisions.id"],
            name="fk_crm_tech_card_revision_same_card_base",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_crm_tech_card_revisions_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            name=op.f("fk_crm_tech_card_revisions_published_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tech_card_id"],
            ["crm_tech_cards.id"],
            name=op.f("fk_crm_tech_card_revisions_tech_card_id_crm_tech_cards"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_tech_card_revisions")),
        sa.UniqueConstraint(
            "tech_card_id",
            "id",
            name="uq_crm_tech_card_revision_card_identity",
        ),
        sa.UniqueConstraint(
            "tech_card_id",
            "revision_number",
            name="uq_crm_tech_card_revision_number",
        ),
    )
    for column in (
        "based_on_revision_id",
        "created_by_user_id",
        "published_by_user_id",
        "status",
        "tech_card_id",
    ):
        op.create_index(
            op.f(f"ix_crm_tech_card_revisions_{column}"),
            "crm_tech_card_revisions",
            [column],
        )
    op.create_index(
        "uq_crm_tech_card_revision_draft",
        "crm_tech_card_revisions",
        ["tech_card_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
        sqlite_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "uq_crm_tech_card_revision_published",
        "crm_tech_card_revisions",
        ["tech_card_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
        sqlite_where=sa.text("status = 'published'"),
    )

    op.create_table(
        "crm_tech_card_checkpoints",
        sa.Column("tech_card_revision_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("stage_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("standard_minutes", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "labor_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
        sa.Column("currency", sa.String(length=3), server_default="RUB", nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position > 0",
            name=op.f("ck_crm_tech_card_checkpoints_crm_tech_card_checkpoint_position_positive"),
        ),
        sa.CheckConstraint(
            "length(trim(stage_code)) > 0",
            name=op.f("ck_crm_tech_card_checkpoints_crm_tech_card_checkpoint_stage_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_crm_tech_card_checkpoints_crm_tech_card_checkpoint_name_nonempty"),
        ),
        sa.CheckConstraint(
            "standard_minutes IS NULL OR standard_minutes > 0",
            name=op.f("ck_crm_tech_card_checkpoints_crm_tech_card_checkpoint_minutes_positive"),
        ),
        sa.CheckConstraint(
            "labor_cost >= 0",
            name=op.f(
                "ck_crm_tech_card_checkpoints_crm_tech_card_checkpoint_labor_cost_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "currency = 'RUB'",
            name=op.f("ck_crm_tech_card_checkpoints_crm_tech_card_checkpoint_currency_rub"),
        ),
        sa.ForeignKeyConstraint(
            ["tech_card_revision_id"],
            ["crm_tech_card_revisions.id"],
            name=op.f("fk_crm_tech_card_checkpoints_tech_card_revision_id_crm_tech_card_revisions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_tech_card_checkpoints")),
        sa.UniqueConstraint(
            "tech_card_revision_id",
            "position",
            name="uq_crm_tech_card_checkpoint_position",
        ),
    )
    op.create_index(
        op.f("ix_crm_tech_card_checkpoints_stage_code"),
        "crm_tech_card_checkpoints",
        ["stage_code"],
    )
    op.create_index(
        op.f("ix_crm_tech_card_checkpoints_tech_card_revision_id"),
        "crm_tech_card_checkpoints",
        ["tech_card_revision_id"],
    )

    op.create_table(
        "crm_reference_events",
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('fabric', 'garment_model', 'catalog_product_link', "
            "'tech_card', 'tech_card_revision')",
            name=op.f("ck_crm_reference_events_crm_reference_event_entity_type_valid"),
        ),
        sa.CheckConstraint(
            "action IN ('created', 'updated', 'linked', 'revision_created', 'published', "
            "'discarded')",
            name=op.f("ck_crm_reference_events_crm_reference_event_action_valid"),
        ),
        sa.CheckConstraint(
            "entity_id > 0",
            name=op.f("ck_crm_reference_events_crm_reference_event_entity_positive"),
        ),
        sa.CheckConstraint(
            "entity_version > 0",
            name=op.f("ck_crm_reference_events_crm_reference_event_version_positive"),
        ),
        sa.CheckConstraint(
            "length(snapshot_sha256) = 64",
            name=op.f("ck_crm_reference_events_crm_reference_event_snapshot_digest_length"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_crm_reference_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_reference_events")),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "entity_version",
            "action",
            name="uq_crm_reference_event_identity",
        ),
    )
    for column in ("action", "actor_user_id", "entity_id", "entity_type", "occurred_at"):
        op.create_index(
            op.f(f"ix_crm_reference_events_{column}"),
            "crm_reference_events",
            [column],
        )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        rows = bind.execute(
            sa.text(
                "SELECT "
                "(SELECT count(*) FROM crm_fabrics) + "
                "(SELECT count(*) FROM crm_garment_models) + "
                "(SELECT count(*) FROM crm_garment_sizes) + "
                "(SELECT count(*) FROM crm_catalog_product_model_links) + "
                "(SELECT count(*) FROM crm_tech_cards) + "
                "(SELECT count(*) FROM crm_tech_card_revisions) + "
                "(SELECT count(*) FROM crm_tech_card_checkpoints) + "
                "(SELECT count(*) FROM crm_reference_events)"
            )
        ).scalar_one()
        if rows:
            raise RuntimeError("Cannot downgrade CRM reference data while durable rows exist")

    for index_name in (
        "ix_crm_reference_events_occurred_at",
        "ix_crm_reference_events_entity_type",
        "ix_crm_reference_events_entity_id",
        "ix_crm_reference_events_actor_user_id",
        "ix_crm_reference_events_action",
    ):
        op.drop_index(index_name, table_name="crm_reference_events")
    op.drop_table("crm_reference_events")
    op.drop_index(
        op.f("ix_crm_tech_card_checkpoints_tech_card_revision_id"),
        table_name="crm_tech_card_checkpoints",
    )
    op.drop_index(
        op.f("ix_crm_tech_card_checkpoints_stage_code"),
        table_name="crm_tech_card_checkpoints",
    )
    op.drop_table("crm_tech_card_checkpoints")
    for index_name in (
        "uq_crm_tech_card_revision_published",
        "uq_crm_tech_card_revision_draft",
        "ix_crm_tech_card_revisions_tech_card_id",
        "ix_crm_tech_card_revisions_status",
        "ix_crm_tech_card_revisions_published_by_user_id",
        "ix_crm_tech_card_revisions_created_by_user_id",
        "ix_crm_tech_card_revisions_based_on_revision_id",
    ):
        op.drop_index(index_name, table_name="crm_tech_card_revisions")
    op.drop_table("crm_tech_card_revisions")
    for index_name in (
        "ix_crm_tech_cards_is_active",
        "ix_crm_tech_cards_garment_model_id",
        "ix_crm_tech_cards_code",
    ):
        op.drop_index(index_name, table_name="crm_tech_cards")
    op.drop_table("crm_tech_cards")
    for index_name in (
        "ix_crm_catalog_product_model_links_garment_model_id",
        "ix_crm_catalog_product_model_links_created_by_user_id",
        "ix_crm_catalog_product_model_links_catalog_product_id",
    ):
        op.drop_index(index_name, table_name="crm_catalog_product_model_links")
    op.drop_table("crm_catalog_product_model_links")
    for index_name in (
        "ix_crm_garment_sizes_model_active_sort",
        "ix_crm_garment_sizes_is_active",
        "ix_crm_garment_sizes_garment_model_id",
        "ix_crm_garment_sizes_code",
    ):
        op.drop_index(index_name, table_name="crm_garment_sizes")
    op.drop_table("crm_garment_sizes")
    for index_name in (
        "ix_crm_garment_models_name",
        "ix_crm_garment_models_is_active",
        "ix_crm_garment_models_code",
    ):
        op.drop_index(index_name, table_name="crm_garment_models")
    op.drop_table("crm_garment_models")
    for index_name in (
        "ix_crm_fabrics_name",
        "ix_crm_fabrics_material_type",
        "ix_crm_fabrics_is_active",
        "ix_crm_fabrics_color_name",
        "ix_crm_fabrics_code",
    ):
        op.drop_index(index_name, table_name="crm_fabrics")
    op.drop_table("crm_fabrics")
