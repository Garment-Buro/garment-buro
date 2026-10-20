"""Editor source is complete or rejected before media hydration, on both databases."""

from decimal import Decimal

import pytest
from sqlalchemy import delete, event, func, insert, inspect, select, update

from app.modules.catalog.admin_service import CatalogAdminReadService
from app.modules.catalog.availability import load_availability
from app.modules.catalog.editor_repository import (
    CatalogEditorRepository,
    CatalogEditorVariantLimitError,
)
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.router import router as catalog_router
from app.modules.media.models import (
    MediaObject,
    ProductMedia,
    ProductMediaRole,
    ProductVariantMedia,
)
from tests.contract.test_reference_directory import ROOT
from tests.contract.test_reference_directory import references as references


@pytest.fixture
def preset_source(references):
    client, prefix, models, fabrics, _, _, tokens = references
    client.app.include_router(catalog_router)

    async def seed():
        async with client.app.state.database.session() as session:
            product = Product(
                title=f"{prefix} source",
                price=Decimal("1234.56"),
                old_price=Decimal("2345.67"),
                description="Description",
                composition="Cotton",
                model_info="Info",
                sizes=["M", "L"],
                colors=["black"],
                tags=["аниме"],
                preset_source="user",
                garment_model_id=models[1],
                is_active=False,
                stock_quantity=17,
                reserved_quantity=2,
                variants=[
                    ProductVariant(
                        sku=f"{prefix}-{i}",
                        size=f"S{i}",
                        color="black",
                        color_hex="#000000",
                        fabric_id=fabrics[1],
                        stock_quantity=7,
                        reserved_quantity=2,
                        width_cm=Decimal("64.25"),
                        height_cm=Decimal("72.35"),
                    )
                    for i in range(200)
                ],
            )
            empty = Product(title=f"{prefix} empty", price=1, stock_quantity=9, variants=[])
            session.add_all([product, empty])
            await session.flush()
            media = [
                MediaObject(
                    bucket_name="catalog",
                    object_key=f"uploads/{prefix}-{i}.webp",
                    size_bytes=10,
                    checksum_sha256="a" * 64,
                    content_type="image/webp",
                    status="ready" if i != 3 else "pending",
                    is_public=i != 4,
                )
                for i in range(5)
            ]
            session.add_all(media)
            await session.flush()
            session.add_all(
                ProductMedia(product_id=product.id, media_object_id=media[0].id, role=role.value)
                for role in ProductMediaRole
            )
            session.add_all(
                ProductMedia(
                    product_id=product.id,
                    media_object_id=media[i].id,
                    role="gallery_images",
                    sort_order=i,
                )
                for i in range(1, 5)
            )
            session.add_all(
                ProductVariantMedia(
                    product_variant_id=product.variants[0].id,
                    media_object_id=media[i].id,
                    role=role,
                    sort_order=i,
                )
                for role in ["preview_image", "images"]
                for i in range(5)
            )
            await session.commit()
            return product.id, empty.id, [row.id for row in media], product.variants[0].id

    product, empty, media, variant = client.portal.call(seed)
    try:
        yield client, product, empty, variant, tokens, prefix
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(delete(Product).where(Product.id.in_([product, empty])))
                await session.execute(delete(MediaObject).where(MediaObject.id.in_(media)))
                await session.commit()

        client.portal.call(cleanup)


def test_complete_200_sku_source_preserves_stock_media_and_scalar_values(preset_source):
    client, product_id, empty_id, variant_id, tokens, prefix = preset_source

    async def scenario():
        mapper = CatalogResponseMapper(client.app.state.settings)
        service = CatalogAdminReadService(mapper)
        async with client.app.state.database.session() as session:
            source = await service.detail(session, product_id)
            assert source.stock_quantity == 17 and source.reserved_quantity == 2
            assert source.available_stock_quantity == 11
            assert len(source.variants) == 200 and source.variants[0].id == variant_id
            assert source.variants[0].sku == f"{prefix}-0"
            assert source.variants[0].stock_quantity == 7
            assert source.variants[0].reserved_quantity == 2
            assert source.variants[0].available_stock_quantity == 11
            assert source.variants[0].width_cm == 64.25 and source.variants[0].height_cm == 72.35
            assert source.tags == ["аниме"] and source.preset_source == "user"
            assert not source.is_active and source.old_price == 2345.67
            urls = [f"/uploads/{prefix}-{i}.webp" for i in range(3)]
            assert source.gallery_images == ",".join(urls)
            assert source.variants[0].images == ",".join(urls)
            assert source.variants[0].preview_image == urls[0]
            assert len(source.media_assets) == len(ProductMediaRole) + 2
            assert "variants" in inspect(await session.get(Product, product_id)).unloaded
            assert "media_links" in inspect(await session.get(ProductVariant, variant_id)).unloaded
            assert not session.new and not session.dirty and not session.deleted
        async with client.app.state.database.session() as session:
            complete = await CatalogRepository().get_product(session, product_id)
            await load_availability(session, [complete])
            public = mapper.product_detail(complete).model_dump(
                exclude={"stock_quantity", "variants"}
            )
            assert public == source.model_dump(
                exclude={
                    "stock_quantity",
                    "reserved_quantity",
                    "available_stock_quantity",
                    "variants",
                }
            )
            for row, expected in zip(source.variants, complete.variants, strict=True):
                assert row.model_dump(
                    exclude={
                        "sku",
                        "garment_size_id",
                        "fabric_id",
                        "reserved_quantity",
                        "available_stock_quantity",
                        "stock_quantity",
                    }
                ) == mapper.variant(expected).model_dump(exclude={"stock_quantity"})
        async with client.app.state.database.session() as session:
            empty = await service.detail(session, empty_id)
            assert empty.variants == [] and empty.media_assets == []
            assert empty.gallery_images is None and empty.available_stock_quantity == 9

    client.portal.call(scenario)
    production = client.get(f"{ROOT}/products/{product_id}")
    identity = client.get(f"/api/products/{product_id}", headers=tokens[0])
    assert production.status_code == identity.status_code == 200
    assert production.json() == identity.json()
    assert production.headers["cache-control"] == identity.headers["cache-control"] == "no-store"
    assert client.get(f"/api/products/{product_id}").status_code == 401
    assert client.get(f"/api/products/{product_id}", headers=tokens[1]).status_code == 403
    missing = client.get(f"{ROOT}/products/2147483647")
    assert missing.status_code == 404 and missing.headers["cache-control"] == "no-store"
    client.cookies.clear()
    assert client.get(f"{ROOT}/products/{product_id}", headers=tokens[0]).status_code == 401


@pytest.mark.parametrize("extra", [1, 19800])
def test_oversized_source_rejected_after_201_rows_without_any_media_read(preset_source, extra):
    client, product_id, _, _, tokens, prefix = preset_source

    async def scenario():
        async with client.app.state.database.session() as session:
            await session.execute(
                insert(ProductVariant),
                [{"product_id": product_id, "sku": f"{prefix}-large-{i}"} for i in range(extra)],
            )
            await session.commit()
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                statements.append((statement, parameters))

        engine = client.app.state.database.engine.sync_engine
        event.listen(engine, "before_cursor_execute", capture)
        try:
            async with client.app.state.database.session() as session:
                with pytest.raises(CatalogEditorVariantLimitError):
                    await CatalogEditorRepository.detail(
                        session, product_id, settings=client.app.state.settings
                    )
                assert len(statements) == 2
                assert "LIMIT" in statements[1][0] and 201 in statements[1][1]
                assert all("media" not in sql.lower() for sql, _ in statements)
                assert not session.new and not session.dirty and not session.deleted
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        async with client.app.state.database.session() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProductVariant)
                    .where(ProductVariant.product_id == product_id)
                )
                == 200 + extra
            )

    client.portal.call(scenario)
    for path, headers in [
        (f"{ROOT}/products/{product_id}", {}),
        (f"/api/products/{product_id}", tokens[0]),
    ]:
        response = client.get(path, headers=headers)
        assert response.status_code == 409, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["detail"]["code"] == "catalog_editor_variant_limit"
        assert "200" in response.json()["detail"]["message"] and "variants" not in response.json()


def test_source_refreshes_cached_product_and_variants_without_assigning_relationships(
    preset_source,
):
    client, product_id, _, variant_id, _, _ = preset_source

    async def scenario():
        async with client.app.state.database.session() as session:
            product = await CatalogRepository().get_product(session, product_id)
            variant = next(row for row in product.variants if row.id == variant_id)
            await session.execute(
                update(Product).where(Product.id == product_id).values(title="Fresh", version=2),
                execution_options={"synchronize_session": False},
            )
            await session.execute(
                update(ProductVariant)
                .where(ProductVariant.id == variant_id)
                .values(width_cm=Decimal("66.75")),
                execution_options={"synchronize_session": False},
            )
            assert product.title != "Fresh" and variant.width_cm == Decimal("64.25")
            source = await CatalogAdminReadService(
                CatalogResponseMapper(client.app.state.settings)
            ).detail(session, product_id)
            assert source.title == "Fresh" and source.version == 2
            assert source.variants[0].width_cm == 66.75
            assert (
                "variants" in inspect(product).unloaded
                and "media_links" in inspect(variant).unloaded
            )
            assert not session.dirty and not session.deleted
            await session.rollback()

    client.portal.call(scenario)
