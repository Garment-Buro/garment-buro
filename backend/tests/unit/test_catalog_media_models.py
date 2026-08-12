from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product
from app.modules.media.models import MediaObject, ProductMedia, ProductMediaRole


def test_catalog_and_media_models_persist_normalized_relations() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with database.session() as session:
            product = Product(
                title="Normalized product",
                price=Decimal("12000.00"),
                sizes=["S", "M"],
                colors=["black", "white"],
                stock_quantity=3,
            )
            media = MediaObject(
                bucket_name="garment-buro-test-media",
                object_key="catalog/2026/product.webp",
                original_filename="product.webp",
                content_type="image/webp",
                size_bytes=10,
                checksum_sha256="a" * 64,
                status="ready",
            )
            product.media_links.append(
                ProductMedia(
                    media=media,
                    role=ProductMediaRole.DESKTOP_SLIDER_IMAGES.value,
                    sort_order=0,
                )
            )
            session.add(product)
            await session.commit()

        async with database.session() as session:
            stored = await session.scalar(
                select(Product).options(
                    selectinload(Product.media_links).selectinload(ProductMedia.media)
                )
            )

        assert stored is not None
        assert stored.sizes == ["S", "M"]
        assert stored.price == Decimal("12000.00")
        assert stored.media_links[0].role == "desktop_slider_images"
        assert stored.media_links[0].media.object_key.endswith("product.webp")
        await database.shutdown()

    asyncio.run(scenario())


def test_catalog_constraints_reject_negative_stock() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        with pytest.raises(IntegrityError):
            async with database.session() as session:
                session.add(
                    Product(
                        title="Invalid stock",
                        price=Decimal("1.00"),
                        sizes=[],
                        colors=[],
                        stock_quantity=-1,
                    )
                )
                await session.commit()

        await database.shutdown()

    asyncio.run(scenario())


def test_product_media_roles_cover_the_legacy_frontend_contract() -> None:
    assert {role.value for role in ProductMediaRole} == {
        "video_src",
        "image_left",
        "image_right",
        "gallery_images",
        "size_chart_img_1",
        "size_chart_img_2",
        "desktop_video",
        "desktop_video_poster",
        "desktop_card_images",
        "desktop_slider_images",
        "mobile_card_image",
        "mobile_video_poster",
        "mobile_slider_images",
        "mobile_product_slider_images",
        "mobile_size_chart_first",
    }
