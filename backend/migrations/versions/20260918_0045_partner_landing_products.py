"""Normalize partner landing products into a relational table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260918_0045"
down_revision: str | Sequence[str] | None = "20260918_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "partner_landing_products",
        sa.Column("landing_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
            "position >= 0",
            name=op.f("ck_partner_landing_products_partner_landing_product_position_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["landing_id"],
            ["partner_landings.id"],
            name=op.f("fk_partner_landing_products_landing_id_partner_landings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_partner_landing_products_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "landing_id",
            "product_id",
            name="uq_partner_landing_product_identity",
        ),
        sa.UniqueConstraint(
            "landing_id",
            "position",
            name="uq_partner_landing_product_position",
        ),
    )
    op.create_index(
        op.f("ix_partner_landing_products_landing_id"),
        "partner_landing_products",
        ["landing_id"],
    )
    op.create_index(
        op.f("ix_partner_landing_products_product_id"),
        "partner_landing_products",
        ["product_id"],
    )

    op.execute(
        sa.text(
            "INSERT INTO partner_landing_products "
            "(landing_id, product_id, position, created_at, updated_at) "
            "SELECT landing.id, product.id, selected.ordinality - 1, now(), now() "
            "FROM partner_landings landing "
            "CROSS JOIN LATERAL jsonb_array_elements_text(landing.product_ids) "
            "WITH ORDINALITY AS selected(product_id, ordinality) "
            "JOIN products product ON product.id = CAST(selected.product_id AS INTEGER)"
        )
    )
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF EXISTS ("
            "SELECT 1 FROM partner_landings landing "
            "WHERE jsonb_array_length(landing.product_ids) <> ("
            "SELECT count(*) FROM partner_landing_products link "
            "WHERE link.landing_id = landing.id"
            ")) THEN "
            "RAISE EXCEPTION 'Partner landing products could not be migrated without data loss'; "
            "END IF; END $$"
        )
    )
    op.drop_column("partner_landings", "product_ids")


def downgrade() -> None:
    op.add_column(
        "partner_landings",
        sa.Column(
            "product_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE partner_landings landing SET product_ids = COALESCE(("
            "SELECT jsonb_agg(link.product_id ORDER BY link.position) "
            "FROM partner_landing_products link WHERE link.landing_id = landing.id"
            "), '[]'::jsonb)"
        )
    )
    op.alter_column("partner_landings", "product_ids", nullable=False)
    op.drop_index(
        op.f("ix_partner_landing_products_product_id"),
        table_name="partner_landing_products",
    )
    op.drop_index(
        op.f("ix_partner_landing_products_landing_id"),
        table_name="partner_landing_products",
    )
    op.drop_table("partner_landing_products")
