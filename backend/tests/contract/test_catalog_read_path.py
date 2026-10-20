from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.base import Base
from app.db.session import DatabaseManager
from app.factory import create_app
from app.integrations.minio import MinioStorage
from app.modules.catalog.cutover import verify_catalog_cutover
from app.modules.catalog.models import CatalogMigrationRun, Product, ProductVariant
from app.modules.media.models import (
    MediaObject,
    MediaStatus,
    ProductMedia,
    ProductMediaRole,
    ProductVariantMedia,
    ProductVariantMediaRole,
)
from tests.fakes.minio import FakeMinioClient
from tests.migration_checks import check_migration


def test_read_only_catalog_exposes_bounded_storefront_without_administrative_routes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.db"
    migration_fingerprint = "d" * 64
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        catalog_reads_enabled=True,
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.test",
    )
    database = DatabaseManager(settings)

    async def seed() -> None:
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with database.session() as session:
            older = Product(
                id=1,
                title="Older product",
                price=Decimal("1000.00"),
                old_price=None,
                description=None,
                composition=None,
                model_info=None,
                sizes=["S", "M"],
                colors=["black", "white"],
                product_type="normal",
                weight_kg=Decimal("0.500"),
                height_cm=Decimal("70.00"),
                width_cm=Decimal("60.00"),
                length_cm=Decimal("72.00"),
                stock_quantity=2,
            )
            current = Product(
                id=2,
                title="Current product",
                price=Decimal("12000.00"),
                old_price=Decimal("15000.00"),
                description="Description",
                composition="Composition",
                model_info="Model info",
                sizes=["XS", "S"],
                colors=["black"],
                product_type="normal",
                weight_kg=Decimal("0.750"),
                height_cm=Decimal("72.00"),
                width_cm=Decimal("64.00"),
                length_cm=Decimal("74.00"),
                stock_quantity=4,
            )
            first_image = MediaObject(
                id=17,
                bucket_name="garment-buro-test-media",
                object_key="uploads/first.webp",
                original_filename="first.webp",
                content_type="image/webp",
                size_bytes=10,
                checksum_sha256="a" * 64,
                status=MediaStatus.READY.value,
            )
            second_image = MediaObject(
                id=18,
                bucket_name="garment-buro-test-media",
                object_key="uploads/second.webp",
                original_filename="second.webp",
                content_type="image/webp",
                size_bytes=11,
                checksum_sha256="b" * 64,
                status=MediaStatus.READY.value,
            )
            current.media_links.extend(
                [
                    ProductMedia(
                        media=second_image,
                        role=ProductMediaRole.DESKTOP_SLIDER_IMAGES.value,
                        sort_order=1,
                    ),
                    ProductMedia(
                        media=first_image,
                        role=ProductMediaRole.DESKTOP_SLIDER_IMAGES.value,
                        sort_order=0,
                    ),
                    ProductMedia(
                        media=first_image,
                        role=ProductMediaRole.MOBILE_CARD_IMAGE.value,
                        sort_order=0,
                    ),
                ]
            )
            variant = ProductVariant(
                id=20,
                size="S",
                color="Черный",
                color_hex="#1A1A1A",
                stock_quantity=3,
                width_cm=Decimal("64.00"),
                height_cm=Decimal("72.00"),
            )
            variant.media_links.append(
                ProductVariantMedia(
                    media=first_image,
                    role=ProductVariantMediaRole.PREVIEW_IMAGE.value,
                    sort_order=0,
                )
            )
            current.variants.append(variant)
            session.add_all(
                [
                    older,
                    current,
                    CatalogMigrationRun(
                        fingerprint_sha256=migration_fingerprint,
                        products_count=2,
                        variants_count=1,
                        media_count=2,
                        media_references_count=4,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(seed())
    storage = MinioStorage(settings, client=FakeMinioClient())
    application = create_app(
        settings=settings,
        database=database,
        storage=storage,
    )

    with TestClient(application) as client:
        assert client.get("/api/products").status_code == 404
        assert client.get("/api/products/2").status_code == 404
        list_response = client.get("/api/catalog/products?sort=newest&limit=1")
        next_response = client.get(
            "/api/catalog/products",
            params={
                "sort": "newest",
                "limit": 1,
                "cursor": list_response.json()["next_cursor"],
            },
        )
        detail_response = client.get("/api/catalog/products/2")
        missing_response = client.get("/api/catalog/products/999")
        redirect_response = client.get(
            "/uploads/first.webp",
            follow_redirects=False,
        )
        write_response = client.post("/api/products", json={})

    assert list_response.status_code == 200
    listed = list_response.json()
    assert [product["id"] for product in listed["items"]] == [2]
    assert listed["next_cursor"]
    assert next_response.status_code == 200
    assert [product["id"] for product in next_response.json()["items"]] == [1]
    assert next_response.json()["next_cursor"] is None

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["schema_version"] == 1
    assert [(item["id"], item["url"]) for item in detail["media_assets"]] == [
        (17, "/uploads/first.webp"),
        (18, "/uploads/second.webp"),
    ]
    assert detail["images"] == [
        {"media_id": 17, "role": "desktop_slider_images", "sort_order": 0},
        {"media_id": 18, "role": "desktop_slider_images", "sort_order": 1},
        {"media_id": 17, "role": "mobile_card_image", "sort_order": 0},
    ]
    assert detail["variants"] == [
        {
            "id": 20,
            "size": "S",
            "color": "Черный",
            "color_hex": "#1A1A1A",
            "stock_quantity": 3,
            "width_cm": 64.0,
            "height_cm": 72.0,
            "images": [{"media_id": 17, "role": "preview_image", "sort_order": 0}],
        }
    ]
    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "Product not found"}
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"] == (
        "https://cdn.test/garment-buro-test-media/uploads/first.webp"
    )
    assert redirect_response.headers["cache-control"] == ("public, max-age=31536000, immutable")
    assert write_response.status_code == 404

    async def tamper_with_migrated_counts() -> None:
        tamper_database = DatabaseManager(settings)
        await tamper_database.startup()
        try:
            async with tamper_database.session() as session:
                await session.execute(update(CatalogMigrationRun).values(products_count=999))
                await session.commit()
        finally:
            await tamper_database.shutdown()

    asyncio.run(tamper_with_migrated_counts())
    with pytest.raises(ConfigurationError, match="counts do not match"):
        check_migration(settings, verify_catalog_cutover, migration_fingerprint)

    with pytest.raises(ConfigurationError, match="not present"):
        check_migration(settings, verify_catalog_cutover, "e" * 64)
