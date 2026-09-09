from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.cutover import verify_catalog_cutover
from app.modules.catalog.models import CatalogMigrationRun, Product
from app.modules.media.models import (
    MediaObject,
    MediaStatus,
    ProductMedia,
)


def test_catalog_cutover_allows_reviewed_writes_after_strict_import(tmp_path: Path) -> None:
    async def scenario() -> None:
        fingerprint = "a" * 64
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'cutover.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                session.add(
                    CatalogMigrationRun(
                        fingerprint_sha256=fingerprint,
                        products_count=0,
                        variants_count=0,
                        media_count=0,
                        media_references_count=0,
                    )
                )
                await session.commit()

            await verify_catalog_cutover(database, fingerprint)

            async with database.session() as session:
                session.add(Product(title="Created after cutover", price=100))
                await session.commit()

            with pytest.raises(ConfigurationError, match="target counts"):
                await verify_catalog_cutover(database, fingerprint)
            await verify_catalog_cutover(database, fingerprint, allow_mutations=True)
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_catalog_cutover_ignores_demo_products_and_private_crm_media(tmp_path: Path) -> None:
    async def scenario() -> None:
        fingerprint = "b" * 64
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'isolated-cutover.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                product = Product(title="Storefront", price=100)
                demo = Product(title="Demo", price=0, is_active=False, is_demo=True)
                session.add_all([product, demo])
                await session.flush()
                catalog_media = _media("catalog.webp", "1")
                private_media = _media("crm/private.webp", "2", is_public=False)
                demo_media = _media("demo.webp", "3", is_public=False)
                session.add_all([catalog_media, private_media, demo_media])
                await session.flush()
                session.add_all(
                    [
                        ProductMedia(
                            product_id=product.id,
                            media_object_id=catalog_media.id,
                            role="gallery_images",
                        ),
                        ProductMedia(
                            product_id=demo.id,
                            media_object_id=demo_media.id,
                            role="gallery_images",
                        ),
                        CatalogMigrationRun(
                            fingerprint_sha256=fingerprint,
                            products_count=1,
                            variants_count=0,
                            media_count=1,
                            media_references_count=1,
                        ),
                    ]
                )
                await session.commit()

            await verify_catalog_cutover(database, fingerprint)

            async with database.session() as session:
                session.add(Product(title="Unexpected storefront item", price=200))
                await session.commit()
            with pytest.raises(ConfigurationError, match="target counts"):
                await verify_catalog_cutover(database, fingerprint)
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_catalog_cutover_accepts_legacy_global_counts_during_transition(tmp_path: Path) -> None:
    async def scenario() -> None:
        fingerprint = "c" * 64
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'legacy-cutover.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                product = Product(title="Storefront", price=100)
                demo = Product(title="Demo", price=0, is_active=False, is_demo=True)
                session.add_all([product, demo])
                await session.flush()
                catalog_media = _media("catalog.webp", "4")
                private_media = _media("crm/private.webp", "5", is_public=False)
                session.add_all([catalog_media, private_media])
                await session.flush()
                session.add(
                    ProductMedia(
                        product_id=product.id,
                        media_object_id=catalog_media.id,
                        role="gallery_images",
                    )
                )
                session.add(
                    CatalogMigrationRun(
                        fingerprint_sha256=fingerprint,
                        products_count=2,
                        variants_count=0,
                        media_count=2,
                        media_references_count=1,
                    )
                )
                await session.commit()

            await verify_catalog_cutover(database, fingerprint)
            await verify_catalog_cutover(database, fingerprint, allow_mutations=True)
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def _media(object_key: str, checksum_seed: str, *, is_public: bool = True) -> MediaObject:
    return MediaObject(
        bucket_name="test",
        object_key=object_key,
        content_type="image/webp",
        size_bytes=1,
        checksum_sha256=checksum_seed * 64,
        is_public=is_public,
        status=MediaStatus.READY.value,
    )
