"""Normalize legacy global catalog counts to the storefront-only baseline."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0040"
down_revision = "20260909_0039"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            """
            WITH scoped AS (
                SELECT
                    (SELECT count(*) FROM products WHERE NOT is_demo) AS products_count,
                    (
                        SELECT count(*)
                        FROM product_variants variants
                        JOIN products ON products.id = variants.product_id
                        WHERE NOT products.is_demo
                    ) AS variants_count,
                    (
                        SELECT count(*)
                        FROM (
                            SELECT product_media.media_object_id
                            FROM product_media
                            JOIN products ON products.id = product_media.product_id
                            WHERE NOT products.is_demo
                            UNION
                            SELECT product_variant_media.media_object_id
                            FROM product_variant_media
                            JOIN product_variants
                                ON product_variants.id = product_variant_media.product_variant_id
                            JOIN products ON products.id = product_variants.product_id
                            WHERE NOT products.is_demo
                        ) AS catalog_media
                    ) AS media_count,
                    (
                        SELECT count(*)
                        FROM product_media
                        JOIN products ON products.id = product_media.product_id
                        WHERE NOT products.is_demo
                    ) + (
                        SELECT count(*)
                        FROM product_variant_media
                        JOIN product_variants
                            ON product_variants.id = product_variant_media.product_variant_id
                        JOIN products ON products.id = product_variants.product_id
                        WHERE NOT products.is_demo
                    ) AS media_references_count
            ),
            legacy AS (
                SELECT
                    (SELECT count(*) FROM products) AS products_count,
                    (SELECT count(*) FROM product_variants) AS variants_count,
                    (SELECT count(*) FROM media_objects) AS media_count,
                    (
                        (SELECT count(*) FROM product_media)
                        + (SELECT count(*) FROM product_variant_media)
                    ) AS media_references_count
            )
            UPDATE catalog_migration_runs
            SET
                products_count = scoped.products_count,
                variants_count = scoped.variants_count,
                media_count = scoped.media_count,
                media_references_count = scoped.media_references_count
            FROM scoped, legacy
            WHERE catalog_migration_runs.products_count = legacy.products_count
              AND catalog_migration_runs.variants_count = legacy.variants_count
              AND catalog_migration_runs.media_count = legacy.media_count
              AND catalog_migration_runs.media_references_count
                  = legacy.media_references_count
            """
        )
    )


def downgrade():
    # The scoped baseline is the correct invariant and remains valid for 0039.
    pass
