from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.config import AppEnvironment, Settings
from app.db import models as database_models  # noqa: F401
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import Product
from app.modules.crm.assortment_schemas import (
    CrmAccessoryCategoryWrite,
    CrmAccessoryWrite,
    CrmGarmentAccessoryRequirementWrite,
    CrmGarmentFabricRequirementWrite,
    CrmGarmentPackagingRuleWrite,
    CrmGarmentPatternWrite,
    CrmPackagingBoxWrite,
)
from app.modules.crm.assortment_service import (
    CrmAssortmentConflictError,
    CrmAssortmentService,
    CrmAssortmentVersionConflictError,
)
from app.modules.crm.reference_schemas import (
    CrmFabricWrite,
    CrmGarmentModelWrite,
    CrmGarmentSizeWrite,
)
from app.modules.crm.reference_service import CrmReferenceConflictError, CrmReferenceService
from app.modules.media.models import (
    MediaObject,
    MediaStatus,
    ProductMedia,
    ProductMediaRole,
)


async def _database(path: Path) -> DatabaseManager:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
    )
    database = DatabaseManager(settings)
    await database.startup()
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return database


def test_assortment_models_patterns_materials_accessories_and_boxes(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = await _database(tmp_path / "assortment.db")
        references = CrmReferenceService()
        assortment = CrmAssortmentService()
        try:
            async with database.session() as session:
                media = MediaObject(
                    provider="minio",
                    bucket_name="private",
                    object_key="patterns/dress-a0.dxf",
                    original_filename="dress-a0.dxf",
                    content_type="application/dxf",
                    size_bytes=1024,
                    checksum_sha256="a" * 64,
                    is_public=False,
                    status=MediaStatus.READY.value,
                )
                size_chart = MediaObject(
                    provider="minio",
                    bucket_name="public",
                    object_key="size-charts/tshirt-base.webp",
                    original_filename="tshirt-base.webp",
                    content_type="image/webp",
                    size_bytes=2048,
                    checksum_sha256="b" * 64,
                    is_public=True,
                    status=MediaStatus.READY.value,
                )
                session.add_all([media, size_chart])
                await session.flush()
                fabric = await references.create_fabric(
                    session,
                    payload=CrmFabricWrite(
                        code="COTTON_BLACK",
                        name="Cotton black",
                        material_type="cotton",
                        color_name="black",
                        width_cm=Decimal("150"),
                        cost_per_meter=Decimal("900"),
                        minimum_stock_meters=Decimal("30"),
                    ),
                    actor_user_id=None,
                )
                model_payload = CrmGarmentModelWrite(
                    code="TSHIRT_BASE",
                    name="T-shirt base",
                    base_size_code="M",
                    fit_model_name="Alex",
                    fit_model_height_cm=Decimal("180"),
                    base_weight_g=Decimal("280"),
                    size_chart_media_object_id=size_chart.id,
                    sizes=[
                        CrmGarmentSizeWrite(
                            code="M",
                            min_width_cm=Decimal("44"),
                            max_width_cm=Decimal("50"),
                            min_length_cm=Decimal("68"),
                            max_length_cm=Decimal("74"),
                            min_height_cm=Decimal("164"),
                            max_height_cm=Decimal("184"),
                            min_sleeve_length_cm=Decimal("20"),
                            max_sleeve_length_cm=Decimal("26"),
                            allow_standard_sleeve=True,
                            allow_height_sleeve=False,
                        )
                    ],
                )
                with pytest.raises(CrmReferenceConflictError, match="ready public media"):
                    await references.create_garment_model(
                        session,
                        payload=model_payload.model_copy(
                            update={"size_chart_media_object_id": media.id}
                        ),
                        actor_user_id=None,
                    )
                model = await references.create_garment_model(
                    session,
                    payload=model_payload,
                    actor_user_id=None,
                )
                assert model.size_chart_media_object_id == size_chart.id
                assert model.base_size_code == "M"
                assert model.fit_model_name == "Alex"
                assert model.fit_model_height_cm == Decimal("180")
                size = model.sizes[0]
                assert size.allow_standard_sleeve is True
                assert size.allow_height_sleeve is False
                pattern_payload = CrmGarmentPatternWrite(
                    code="PAT-TSHIRT-M-001",
                    garment_model_id=model.id,
                    garment_size_id=size.id,
                    media_object_id=media.id,
                    name="M 46×70 sleeve 22",
                    width_cm=Decimal("46"),
                    length_cm=Decimal("70"),
                    sleeve_length_cm=Decimal("22"),
                    height_cm=Decimal("168"),
                )
                pattern = await assortment.create_pattern(session, pattern_payload)
                assert pattern.grid_key == "M:46.00:70.00:22.00:168.00"
                assert pattern.code == "PAT-TSHIRT-M-001"
                assert [
                    item.id
                    for item in await assortment.list_patterns(
                        session,
                        model_id=None,
                        active=None,
                        query="tshirt-m-001",
                    )
                ] == [pattern.id]

                with pytest.raises(CrmAssortmentConflictError, match="2 cm grid"):
                    await assortment.create_pattern(
                        session,
                        pattern_payload.model_copy(
                            update={"width_cm": Decimal("47"), "name": "Invalid grid"}
                        ),
                    )

                requirement = await assortment.create_fabric_requirement(
                    session,
                    CrmGarmentFabricRequirementWrite(
                        garment_model_id=model.id,
                        fabric_id=fabric.id,
                        meters_per_unit=Decimal("1.350"),
                        waste_percent=Decimal("7.50"),
                        is_primary=True,
                    ),
                )
                assert requirement.meters_per_unit == Decimal("1.350")

                category = await assortment.create_category(
                    session,
                    CrmAccessoryCategoryWrite(code="FASTENERS", name="Fasteners"),
                )
                accessory = await assortment.create_accessory(
                    session,
                    CrmAccessoryWrite(
                        category_id=category.id,
                        code="ZIP_BLACK_20",
                        name="Black zip 20 cm",
                        unit_cost=Decimal("45"),
                        stock_quantity=100,
                        minimum_stock_quantity=20,
                    ),
                )
                await assortment.create_accessory_requirement(
                    session,
                    CrmGarmentAccessoryRequirementWrite(
                        garment_model_id=model.id,
                        accessory_id=accessory.id,
                        quantity_per_unit=Decimal("1"),
                    ),
                )
                box = await assortment.create_box(
                    session,
                    CrmPackagingBoxWrite(
                        code="BOX_S",
                        name="Small box",
                        inner_length_cm=Decimal("30"),
                        inner_width_cm=Decimal("20"),
                        inner_height_cm=Decimal("10"),
                        max_items=2,
                        unit_cost=Decimal("55"),
                        stock_quantity=50,
                        minimum_stock_quantity=10,
                    ),
                )
                assert box.max_items == 2
                packaging_rule = await assortment.create_packaging_rule(
                    session,
                    CrmGarmentPackagingRuleWrite(
                        garment_model_id=model.id,
                        box_id=box.id,
                        max_items=1,
                        priority=10,
                    ),
                )
                assert packaging_rule.max_items == 1

                with pytest.raises(CrmAssortmentConflictError, match="box capacity"):
                    await assortment.create_packaging_rule(
                        session,
                        CrmGarmentPackagingRuleWrite(
                            garment_model_id=model.id,
                            box_id=box.id,
                            max_items=3,
                        ),
                    )

                with pytest.raises(CrmAssortmentVersionConflictError):
                    await assortment.update_box(
                        session,
                        box_id=box.id,
                        expected_version=2,
                        payload=CrmPackagingBoxWrite.model_validate(box.model_dump()),
                    )
                await session.commit()

            async with database.session() as session:
                accessories = await assortment.list_accessories(
                    session,
                    category_id=None,
                    model_id=model.id,
                    active=True,
                )
                assert len(accessories) == 1
                assert accessories[0].model_ids == [model.id]
                boxes = await assortment.list_boxes(session, active=True)
                assert boxes[0].stock_quantity == 50
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_product_references_include_admin_card_image(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = await _database(tmp_path / "assortment-products.db")
        try:
            async with database.session() as session:
                image = MediaObject(
                    provider="minio",
                    bucket_name="public",
                    object_key="uploads/catalog-card.webp",
                    original_filename="catalog-card.webp",
                    content_type="image/webp",
                    size_bytes=1024,
                    checksum_sha256="c" * 64,
                    is_public=True,
                    status=MediaStatus.READY.value,
                )
                product = Product(
                    title="Catalog card",
                    price=Decimal("3500.00"),
                    stock_quantity=4,
                )
                session.add_all([image, product])
                await session.flush()
                session.add(
                    ProductMedia(
                        product_id=product.id,
                        media_object_id=image.id,
                        role=ProductMediaRole.IMAGE_LEFT.value,
                        sort_order=0,
                    )
                )
                await session.commit()

            async with database.session() as session:
                products = await CrmAssortmentService().list_products(
                    session,
                    model_id=None,
                    category_id=None,
                    active=None,
                    mapper=CatalogResponseMapper(database.settings),
                )
                assert products[0].image_url == "/uploads/catalog-card.webp"
        finally:
            await database.shutdown()

    asyncio.run(scenario())
