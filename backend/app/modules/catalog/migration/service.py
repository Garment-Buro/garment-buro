from __future__ import annotations

import hashlib
from pathlib import Path

from anyio import to_thread
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.minio import MinioStorage, StoredObject
from app.modules.catalog.migration.types import (
    CatalogMigrationPlan,
    CatalogMigrationResult,
    InvalidMigrationPlanError,
    LegacyMediaAsset,
    LegacyMediaReference,
    LegacyProductRecord,
    LegacyVariantRecord,
    TargetCatalogNotEmptyError,
)
from app.modules.catalog.models import CatalogMigrationRun, Product, ProductVariant
from app.modules.media.models import (
    MediaObject,
    MediaStatus,
    ProductMedia,
    ProductVariantMedia,
)
from app.modules.media.service import PreparedMedia, prepare_catalog_media


class CatalogMigrationService:
    def __init__(self, storage: MinioStorage) -> None:
        self.storage = storage

    async def apply(
        self,
        session: AsyncSession,
        plan: CatalogMigrationPlan,
    ) -> CatalogMigrationResult:
        if not plan.valid:
            raise InvalidMigrationPlanError("Migration plan contains validation errors")
        await self._ensure_target_empty(session)

        stored_objects: dict[str, StoredObject] = {}
        for asset in plan.assets:
            source_data = await to_thread.run_sync(Path(asset.source_path).read_bytes)
            prepared = await to_thread.run_sync(prepare_catalog_media, source_data)
            self._verify_asset_unchanged(asset, prepared)
            stored_objects[asset.source_url] = await self.storage.put_object(
                object_key=asset.target_key,
                data=prepared.data,
                content_type=prepared.content_type,
            )

        media_models = self._media_models(plan.assets, stored_objects)
        products = self._product_models(plan.products)
        variants = self._variant_models(plan.variants)
        self._attach_references(plan.references, products, variants, media_models)

        session.add_all(products.values())
        session.add(
            CatalogMigrationRun(
                fingerprint_sha256=plan.fingerprint,
                products_count=len(products),
                variants_count=len(variants),
                media_count=len(media_models),
                media_references_count=len(plan.references),
            )
        )
        await session.flush()
        await self._synchronize_postgresql_sequences(session)
        await session.commit()

        return CatalogMigrationResult(
            fingerprint_sha256=plan.fingerprint,
            products=len(products),
            variants=len(variants),
            media_assets=len(media_models),
            media_references=len(plan.references),
        )

    @staticmethod
    async def _ensure_target_empty(session: AsyncSession) -> None:
        counts = {
            "products": await session.scalar(select(func.count()).select_from(Product)),
            "variants": await session.scalar(select(func.count()).select_from(ProductVariant)),
            "media": await session.scalar(select(func.count()).select_from(MediaObject)),
            "migration_runs": await session.scalar(
                select(func.count()).select_from(CatalogMigrationRun)
            ),
        }
        if any(counts.values()):
            rendered = ", ".join(f"{name}={count}" for name, count in counts.items())
            raise TargetCatalogNotEmptyError(
                f"Target catalog must be empty before import ({rendered})"
            )

    @staticmethod
    def _media_models(
        assets: tuple[LegacyMediaAsset, ...],
        stored_objects: dict[str, StoredObject],
    ) -> dict[str, MediaObject]:
        return {
            asset.source_url: MediaObject(
                provider="minio",
                bucket_name=stored_objects[asset.source_url].bucket_name,
                object_key=stored_objects[asset.source_url].object_key,
                original_filename=Path(asset.source_path).name,
                content_type=asset.content_type,
                size_bytes=asset.size_bytes,
                checksum_sha256=asset.checksum_sha256,
                etag=stored_objects[asset.source_url].etag,
                version_id=stored_objects[asset.source_url].version_id,
                is_public=True,
                status=MediaStatus.READY.value,
            )
            for asset in assets
        }

    @staticmethod
    def _product_models(
        records: tuple[LegacyProductRecord, ...],
    ) -> dict[int, Product]:
        return {
            record.id: Product(
                id=record.id,
                title=record.title,
                price=record.price,
                old_price=record.old_price,
                description=record.description,
                composition=record.composition,
                model_info=record.model_info,
                sizes=list(record.sizes),
                colors=list(record.colors),
                is_active=record.is_active,
                product_type=record.product_type,
                weight_kg=record.weight_kg,
                height_cm=record.height_cm,
                width_cm=record.width_cm,
                length_cm=record.length_cm,
                stock_quantity=record.stock_quantity,
            )
            for record in records
        }

    @staticmethod
    def _variant_models(
        records: tuple[LegacyVariantRecord, ...],
    ) -> dict[int, ProductVariant]:
        return {
            record.id: ProductVariant(
                id=record.id,
                product_id=record.product_id,
                size=record.size,
                color=record.color,
                color_hex=record.color_hex,
                stock_quantity=record.stock_quantity,
                width_cm=record.width_cm,
                height_cm=record.height_cm,
            )
            for record in records
        }

    @staticmethod
    def _attach_references(
        references: tuple[LegacyMediaReference, ...],
        products: dict[int, Product],
        variants: dict[int, ProductVariant],
        media: dict[str, MediaObject],
    ) -> None:
        for variant in variants.values():
            products[variant.product_id].variants.append(variant)
        for reference in references:
            if reference.owner_type == "product":
                products[reference.owner_id].media_links.append(
                    ProductMedia(
                        media=media[reference.source_url],
                        role=reference.role,
                        sort_order=reference.sort_order,
                    )
                )
            else:
                variants[reference.owner_id].media_links.append(
                    ProductVariantMedia(
                        media=media[reference.source_url],
                        role=reference.role,
                        sort_order=reference.sort_order,
                    )
                )

    @staticmethod
    def _verify_asset_unchanged(
        expected: LegacyMediaAsset,
        prepared: PreparedMedia,
    ) -> None:
        checksum = hashlib.sha256(prepared.data).hexdigest()
        if (
            prepared.content_type != expected.content_type
            or len(prepared.data) != expected.size_bytes
            or checksum != expected.checksum_sha256
        ):
            raise InvalidMigrationPlanError(
                f"Source media changed after dry-run: {expected.source_url}"
            )

    @staticmethod
    async def _synchronize_postgresql_sequences(session: AsyncSession) -> None:
        bind = session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        for table_name in (
            "products",
            "product_variants",
            "media_objects",
            "product_media",
            "product_variant_media",
            "catalog_migration_runs",
        ):
            await session.execute(
                text(
                    "SELECT setval("
                    f"pg_get_serial_sequence('{table_name}', 'id'), "
                    f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table_name}"
                )
            )
