from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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

        actual_counts = await _reviewed_catalog_counts(session)
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
                # Compatibility for one deployment while an existing database still
                # stores the former global counts. Normalize the migration record
                # after this version has been verified and before adding more media.
                if await _legacy_global_counts(session) == expected_counts:
                    return
                raise ConfigurationError(
                    "Writable catalog no longer contains the reviewed migration media baseline"
                )
            return
        if actual_counts != expected_counts:
            if await _legacy_global_counts(session) == expected_counts:
                return
            raise ConfigurationError(
                "Catalog target counts do not match the reviewed migration run: "
                f"expected={expected_counts}, actual={actual_counts}"
            )


async def _reviewed_catalog_counts(session: AsyncSession) -> dict[str, int]:
    product_media_ids = (
        select(ProductMedia.media_object_id.label("media_object_id"))
        .join(Product, Product.id == ProductMedia.product_id)
        .where(Product.is_demo.is_(False))
    )
    variant_media_ids = (
        select(ProductVariantMedia.media_object_id.label("media_object_id"))
        .join(
            ProductVariant,
            ProductVariant.id == ProductVariantMedia.product_variant_id,
        )
        .join(Product, Product.id == ProductVariant.product_id)
        .where(Product.is_demo.is_(False))
    )
    catalog_media_ids = product_media_ids.union(variant_media_ids).subquery()
    media_query = (
        select(func.count())
        .select_from(MediaObject)
        .join(
            catalog_media_ids,
            catalog_media_ids.c.media_object_id == MediaObject.id,
        )
    )
    return {
        "products": _count(
            await session.scalar(
                select(func.count()).select_from(Product).where(Product.is_demo.is_(False))
            )
        ),
        "variants": _count(
            await session.scalar(
                select(func.count())
                .select_from(ProductVariant)
                .join(Product, Product.id == ProductVariant.product_id)
                .where(Product.is_demo.is_(False))
            )
        ),
        "media": _count(await session.scalar(media_query)),
        "ready_media": _count(
            await session.scalar(media_query.where(MediaObject.status == MediaStatus.READY.value))
        ),
        "media_references": _count(
            await session.scalar(
                select(func.count())
                .select_from(ProductMedia)
                .join(Product, Product.id == ProductMedia.product_id)
                .where(Product.is_demo.is_(False))
            )
        )
        + _count(
            await session.scalar(
                select(func.count())
                .select_from(ProductVariantMedia)
                .join(
                    ProductVariant,
                    ProductVariant.id == ProductVariantMedia.product_variant_id,
                )
                .join(Product, Product.id == ProductVariant.product_id)
                .where(Product.is_demo.is_(False))
            )
        ),
    }


async def _legacy_global_counts(session: AsyncSession) -> dict[str, int]:
    return {
        "products": _count(await session.scalar(select(func.count()).select_from(Product))),
        "variants": _count(await session.scalar(select(func.count()).select_from(ProductVariant))),
        "media": _count(await session.scalar(select(func.count()).select_from(MediaObject))),
        "ready_media": _count(
            await session.scalar(
                select(func.count())
                .select_from(MediaObject)
                .where(MediaObject.status == MediaStatus.READY.value)
            )
        ),
        "media_references": _count(
            await session.scalar(select(func.count()).select_from(ProductMedia))
        )
        + _count(await session.scalar(select(func.count()).select_from(ProductVariantMedia))),
    }


def _count(value: int | None) -> int:
    return int(value or 0)
