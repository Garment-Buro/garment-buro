from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import ConfigurationError
from app.db.session import DatabaseManager
from app.modules.catalog.models import CatalogMigrationRun, Product, ProductVariant
from app.modules.media.models import (
    MediaObject,
    MediaStatus,
    ProductMedia,
    ProductVariantMedia,
)


async def verify_catalog_cutover(
    database: DatabaseManager,
    expected_fingerprint: str,
    *,
    allow_mutations: bool = False,
) -> None:
    async with database.session() as session:
        migration = await session.scalar(
            select(CatalogMigrationRun).where(
                CatalogMigrationRun.fingerprint_sha256 == expected_fingerprint
            )
        )
        if migration is None:
            raise ConfigurationError(
                "CATALOG_MIGRATION_FINGERPRINT is not present in the target database"
            )

        actual_counts = {
            "products": await session.scalar(select(func.count()).select_from(Product)),
            "variants": await session.scalar(select(func.count()).select_from(ProductVariant)),
            "media": await session.scalar(select(func.count()).select_from(MediaObject)),
            "ready_media": await session.scalar(
                select(func.count())
                .select_from(MediaObject)
                .where(MediaObject.status == MediaStatus.READY.value)
            ),
            "media_references": (
                await session.scalar(select(func.count()).select_from(ProductMedia))
                + await session.scalar(select(func.count()).select_from(ProductVariantMedia))
            ),
        }
        expected_counts = {
            "products": migration.products_count,
            "variants": migration.variants_count,
            "media": migration.media_count,
            "ready_media": migration.media_count,
            "media_references": migration.media_references_count,
        }
        if allow_mutations:
            if (
                actual_counts["media"] < migration.media_count
                or actual_counts["ready_media"] < migration.media_count
            ):
                raise ConfigurationError(
                    "Writable catalog no longer contains the reviewed migration media baseline"
                )
            return
        if actual_counts != expected_counts:
            raise ConfigurationError(
                "Catalog target counts do not match the reviewed migration run: "
                f"expected={expected_counts}, actual={actual_counts}"
            )
