from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, insert, inspect, select, text, update
from sqlalchemy.orm import Session

from app.db.session import DatabaseManager
from app.factory import create_app
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import Product, ProductCategory, ProductVariant
from app.modules.catalog.service import CatalogService
from app.modules.customer_projects.models import CustomerProject
from app.modules.identity.models import User
from app.modules.media.models import MediaObject, ProductMedia, ProductVariantMedia
from app.observability.logging import request_id_context
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.postgres_schema import migrate
from tests.projects_scenario import project_payload

CATALOG = "/api/catalog/products"
COLLECTION = "/api/catalog/collection-products"


def test_constructor_registry_keeps_all_variants_without_editable_or_hidden_source(
    storefront_setup, tmp_path
):
    client, products, _, tokens = storefront_setup
    extra_media, project_ids = [], []

    async def seed():
        database = DatabaseManager(client.app.state.settings)
        await database.startup()
        try:
            async with database.session() as session:
                product = await session.get(Product, products[0])
                product.description = "Not constructor data " * 10000
                assets = []
                for key, public, status, content_type in (
                    ("uploads/variant, front photo.webp", True, "ready", "image/webp"),
                    ("private-variant.webp", False, "ready", "image/webp"),
                    ("pending-variant.webp", True, "pending", "image/webp"),
                    ("variant-video.webm", True, "ready", "video/webm"),
                ):
                    asset = MediaObject(
                        bucket_name="catalog",
                        object_key=key,
                        is_public=public,
                        status=status,
                        content_type=content_type,
                        size_bytes=100,
                        checksum_sha256="b" * 64,
                    )
                    session.add(asset)
                    await session.flush()
                    assets.append(asset)
                    extra_media.append(asset.id)
                for index in range(240):
                    variant = ProductVariant(
                        product_id=product.id,
                        size="M",
                        color=f"color-{index:03d}",
                        stock_quantity=3,
                        reserved_quantity=1,
                        width_cm=60,
                        height_cm=75,
                    )
                    session.add(variant)
                    await session.flush()
                    for order, asset in enumerate(assets):
                        session.add(
                            ProductVariantMedia(
                                product_variant_id=variant.id,
                                media_object_id=asset.id,
                                role="images",
                                sort_order=order,
                            )
                        )
                    session.add(
                        ProductVariantMedia(
                            product_variant_id=variant.id,
                            media_object_id=assets[0].id,
                            role="preview_image",
                            sort_order=0,
                        )
                    )
                await session.commit()
            async with database.session() as session:
                old = await CatalogService(
                    CatalogResponseMapper(client.app.state.settings)
                ).get_product(session, products[0], public_only=True)
                return len(old.model_dump_json().encode())
        finally:
            await database.shutdown()

    async def cleanup():
        database = DatabaseManager(client.app.state.settings)
        await database.startup()
        try:
            async with database.session() as session:
                await session.execute(
                    delete(CustomerProject).where(CustomerProject.id.in_(project_ids))
                )
                await session.execute(
                    delete(ProductVariantMedia).where(
                        ProductVariantMedia.media_object_id.in_(extra_media)
                    )
                )
                await session.execute(delete(MediaObject).where(MediaObject.id.in_(extra_media)))
                await session.commit()
        finally:
            await database.shutdown()

    loaded, statements = [], []

    def capture_entity(session, value):
        if request_id_context.get() == "constructor-registry":
            loaded.append(value)

    def capture_sql(connection, cursor, statement, parameters, context, executemany):
        if request_id_context.get() == "constructor-registry":
            statements.append(statement)

    try:
        before = asyncio.run(seed())
        engine = client.app.state.database.engine.sync_engine
        event.listen(Session, "loaded_as_persistent", capture_entity)
        event.listen(engine, "before_cursor_execute", capture_sql)
        try:
            response = client.get(
                f"{CATALOG}/{products[0]}", headers={"X-Request-ID": "constructor-registry"}
            )
        finally:
            event.remove(Session, "loaded_as_persistent", capture_entity)
            event.remove(engine, "before_cursor_execute", capture_sql)
        assert response.status_code == 200, response.text
        detail = response.json()
        assert set(detail) == {
            "schema_version",
            "id",
            "title",
            "price",
            "sizes",
            "stock_quantity",
            "images",
            "variants",
            "media_assets",
        }
        assert len(detail["variants"]) == 240
        assert all(
            variant["stock_quantity"] == 2 and len(variant["images"]) == 2
            for variant in detail["variants"]
        )
        asset_ids = [asset["id"] for asset in detail["media_assets"]]
        assert len(set(asset_ids)) == len(asset_ids)
        assert extra_media[0] in asset_ids and not set(extra_media[1:]) & set(asset_ids)
        assert (
            next(asset["url"] for asset in detail["media_assets"] if asset["id"] == extra_media[0])
            == "/uploads/variant%2C%20front%20photo.webp"
        )
        assert not any(
            isinstance(row, (ProductMedia, ProductVariantMedia, MediaObject)) for row in loaded
        )
        product = next(row for row in loaded if isinstance(row, Product))
        assert {
            "description",
            "composition",
            "model_info",
            "tags",
            "media_links",
            "variants",
        } <= inspect(product).unloaded
        assert len(statements) == 4
        assert len(response.content) < before / 2
        (tmp_path / "constructor-payload.json").write_text(
            json.dumps(
                {
                    "beforeBytes": before,
                    "afterBytes": len(response.content),
                    "variants": 240,
                    "assets": len(asset_ids),
                    "queries": len(statements),
                }
            )
        )

        # A SKU-only image can be retained by its product's project, never by another product.
        for product_id, status in ((products[0], 201), (products[1], 422)):
            created = client.post(
                "/api/profile/projects",
                headers=tokens[0],
                json=project_payload(product_id, extra_media[0], key=f"variant-{product_id}"),
            )
            assert created.status_code == status, created.text
            if status == 201:
                project_ids.append(created.json()["id"])
        for media_id in extra_media[1:]:
            rejected = client.post(
                "/api/profile/projects",
                headers=tokens[0],
                json=project_payload(products[0], media_id, key=f"rejected-variant-{media_id}"),
            )
            assert rejected.status_code == 422, rejected.text
    finally:
        asyncio.run(cleanup())


def test_constructor_detail_uses_current_public_policy_and_only_public_ready_images(
    storefront_setup,
):
    client, products, _, _ = storefront_setup

    async def add_variant():
        database = DatabaseManager(client.app.state.settings)
        await database.startup()
        try:
            async with database.session() as session:
                images = list(
                    await session.scalars(
                        select(MediaObject)
                        .join(ProductMedia)
                        .where(
                            ProductMedia.product_id == products[0],
                            ProductMedia.role == "mobile_card_image",
                        )
                        .order_by(MediaObject.id)
                    )
                )
                variant = ProductVariant(
                    product_id=products[0],
                    size="M",
                    color="Black",
                    stock_quantity=3,
                    width_cm=60,
                    height_cm=70,
                )
                session.add(variant)
                await session.flush()
                for index, media in enumerate(images):
                    session.add(
                        ProductVariantMedia(
                            product_variant_id=variant.id,
                            media_object_id=media.id,
                            role="preview_image",
                            sort_order=index,
                        )
                    )
                await session.commit()
        finally:
            await database.shutdown()

    asyncio.run(add_variant())
    response = client.get(f"{CATALOG}/{products[0]}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    detail = response.json()
    assert detail["id"] == products[0]
    assert detail["schema_version"] == 1
    registry = {asset["id"]: asset["url"] for asset in detail["media_assets"]}
    card = next(image for image in detail["images"] if image["role"] == "mobile_card_image")
    assert registry[card["media_id"]].endswith("/front/card.png")
    assert detail["variants"][0]["size"] == "M"
    assert detail["variants"][0]["width_cm"] == 60
    preview = detail["variants"][0]["images"][0]
    assert registry[preview["media_id"]].endswith("/front/card.png")
    assert detail["media_assets"]
    assert "private.png" not in json.dumps(detail)
    assert "pending.png" not in json.dumps(detail)

    async def withdraw():
        database = DatabaseManager(client.app.state.settings)
        await database.startup()
        try:
            async with database.session() as session:
                await session.execute(
                    update(Product).where(Product.id == products[0]).values(is_active=False)
                )
                await session.commit()
        finally:
            await database.shutdown()

    asyncio.run(withdraw())
    withdrawn = client.get(f"{CATALOG}/{products[0]}")
    assert withdrawn.status_code == 404
    assert withdrawn.headers["cache-control"] == "no-store"


def test_constructor_detail_hides_demo_hidden_and_missing_products_without_dependent_reads(
    storefront_setup,
):
    client, products, _, _ = storefront_setup
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if request_id_context.get() == "constructor-unavailable":
            statements.append(statement.lower())

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        for product_id in [*products[3:], 2147483647]:
            statements.clear()
            response = client.get(
                f"{CATALOG}/{product_id}", headers={"X-Request-ID": "constructor-unavailable"}
            )
            assert response.status_code == 404
            assert response.headers["cache-control"] == "no-store"
            assert len(statements) == 1
            assert "products.id =" in statements[0]
    finally:
        event.remove(engine, "before_cursor_execute", capture)


@pytest.mark.parametrize("product_id", ["0", "-1", "2147483648", "NaN"])
def test_constructor_detail_rejects_invalid_ids(storefront_setup, product_id):
    client, _, _, _ = storefront_setup
    assert client.get(f"{CATALOG}/{product_id}").status_code == 422


def test_collection_reads_only_selected_public_models_in_configured_order(storefront_setup):
    client, products, _, _ = storefront_setup
    response = client.get(
        COLLECTION,
        params={
            "ids": [products[2], products[0], products[2], products[1], *products[3:], 2147483647]
        },
    )
    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [products[2], products[0], products[1]]
    assert rows[1] == {
        "id": products[0],
        "title": "Футболка 100%",
        "price": "3000.50",
        "description": "Not needed in product cards",
        "image_url": "https://media.example.test/catalog/front/card.png",
        "image_alt": "Real product photo",
    }
    assert rows[0]["image_url"] is None


def test_collection_prefers_safe_posters_without_changing_storefront_image_priority(
    storefront_setup,
):
    client, products, _, _ = storefront_setup

    async def add_posters():
        database = DatabaseManager(client.app.state.settings)
        await database.startup()
        try:
            async with database.session() as session:
                for index, (key, public, status, role) in enumerate(
                    [
                        ("private-poster.png", False, "ready", "desktop_video_poster"),
                        ("pending-poster.png", True, "pending", "desktop_video_poster"),
                        ("mobile-poster.png", True, "ready", "mobile_video_poster"),
                        ("desktop poster.png", True, "ready", "desktop_video_poster"),
                    ]
                ):
                    media = MediaObject(
                        bucket_name="catalog",
                        object_key=key,
                        content_type="image/png",
                        size_bytes=10,
                        checksum_sha256="b" * 64,
                        is_public=public,
                        status=status,
                    )
                    session.add(media)
                    await session.flush()
                    session.add(
                        ProductMedia(
                            product_id=products[0],
                            media_object_id=media.id,
                            role=role,
                            sort_order=index,
                        )
                    )
                await session.commit()
        finally:
            await database.shutdown()

    asyncio.run(add_posters())
    response = client.get(COLLECTION, params={"ids": products[:1]})
    assert response.status_code == 200
    assert (
        response.json()[0]["image_url"] == "https://media.example.test/catalog/desktop%20poster.png"
    )
    assert (
        client.get(CATALOG, params={"ids": products[:1]}).json()["items"][0]["image_url"]
        == "https://media.example.test/catalog/front/card.png"
    )


def test_card_image_passes_long_ineligible_prefix_and_rechecks_current_visibility(
    storefront_setup,
):
    client, products, _, _ = storefront_setup
    settings = client.app.state.settings

    async def seed_prefix():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                await session.execute(
                    update(MediaObject)
                    .where(
                        MediaObject.id.in_(
                            select(ProductMedia.media_object_id).where(
                                ProductMedia.product_id == products[0],
                                ProductMedia.role == "mobile_card_image",
                            )
                        )
                    )
                    .values(is_public=False)
                )
                media_ids = []
                shapes = [
                    (True, "ready", "video/mp4"),
                    (False, "ready", "image/png"),
                    (True, "pending", "image/png"),
                    (True, "failed", "image/png"),
                    (True, "deleted", "image/png"),
                ]
                for index in range(301):
                    public, status, content_type = (
                        shapes[index % len(shapes)] if index < 300 else (True, "ready", "image/png")
                    )
                    media = MediaObject(
                        bucket_name="catalog",
                        object_key=f"card-prefix/{products[0]}/{index}.png",
                        content_type=content_type,
                        size_bytes=10,
                        checksum_sha256="c" * 64,
                        is_public=public,
                        status=status,
                    )
                    session.add(media)
                    await session.flush()
                    media_ids.append(media.id)
                    session.add(
                        ProductMedia(
                            product_id=products[0],
                            media_object_id=media.id,
                            role="mobile_card_image",
                            sort_order=1000 + index,
                            alt_text=f"Prefix {index}",
                        )
                    )
                await session.commit()
                return media_ids[0], media_ids[-1]
        finally:
            await database.shutdown()

    first_id, winner_id = asyncio.run(seed_prefix())

    def card():
        response = client.get(CATALOG, params={"ids": products[:1]})
        assert response.status_code == 200
        return response.json()["items"][0]

    assert card()["image_url"].endswith(f"/card-prefix/{products[0]}/300.png")
    assert card()["image_alt"] == "Prefix 300"

    async def change(media_id, **fields):
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                await session.execute(
                    update(MediaObject).where(MediaObject.id == media_id).values(**fields)
                )
                await session.commit()
        finally:
            await database.shutdown()

    asyncio.run(change(winner_id, is_public=False))
    assert card()["image_url"].endswith("/uploads/first%20card.png")
    asyncio.run(change(first_id, is_public=True, status="ready", content_type="image/png"))
    assert card()["image_url"].endswith(f"/card-prefix/{products[0]}/0.png")


@pytest.mark.parametrize(
    "params", [{}, {"ids": [0]}, {"ids": [-1]}, {"ids": [2147483648]}, {"ids": [1] * 51}]
)
def test_collection_rejects_unbounded_or_invalid_ids_before_querying_products(
    storefront_setup, params
):
    client, _, _, _ = storefront_setup
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if request_id_context.get() == "collection-invalid":
            statements.append(statement)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert (
            client.get(
                COLLECTION, params=params, headers={"X-Request-ID": "collection-invalid"}
            ).status_code
            == 422
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert statements == []


def test_collection_uses_two_bounded_queries_and_missing_ids_do_not_load_catalog(storefront_setup):
    client, products, _, _ = storefront_setup
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if request_id_context.get() == "collection-query-count":
            statements.append(statement.lower())

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get(
            COLLECTION,
            params={"ids": products[:2]},
            headers={"X-Request-ID": "collection-query-count"},
        )
        assert response.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 2
    assert "products.id in" in statements[0]
    assert "limit" in statements[0]
    assert not any("product_variants" in sql for sql in statements)
    assert client.get(COLLECTION, params={"ids": [2147483647]}).json() == []


async def seed_storefront(settings, products):
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            category = ProductCategory(slug="shirts", name="Футболки")
            session.add(category)
            await session.flush()
            for index, product_id in enumerate(products[:3]):
                product = await session.get(Product, product_id)
                product.title = ["Футболка 100%", "Худи", "Футболка_летняя"][index]
                product.price = Decimal("3000.50") if index < 2 else Decimal("8000.00")
                product.category_id = category.id if index != 1 else None
                product.colors = [["Чёрный", "Белый"], ["Серый"], ["Белый"]][index]
                product.tags = [["Хлопок"], ["Зима"], []][index]
                product.preset_source = "user" if index == 1 else "garment_buro"
                product.description = "Not needed in product cards"
            for index, (key, public, status, content_type, role) in enumerate(
                [
                    ("private.png", False, "ready", "image/png", "mobile_card_image"),
                    ("pending.png", True, "pending", "image/png", "mobile_card_image"),
                    ("video.mp4", True, "ready", "video/mp4", "video_src"),
                    ("uploads/first card.png", True, "ready", "image/png", "gallery_images"),
                    ("front/card.png", True, "ready", "image/png", "mobile_card_image"),
                ]
            ):
                media = MediaObject(
                    bucket_name="catalog",
                    object_key=key,
                    content_type=content_type,
                    size_bytes=100,
                    checksum_sha256="a" * 64,
                    is_public=public,
                    status=status,
                )
                session.add(media)
                await session.flush()
                session.add(
                    ProductMedia(
                        product_id=products[0],
                        media_object_id=media.id,
                        role=role,
                        sort_order=index,
                        alt_text="Real product photo",
                    )
                )
            await session.commit()
            return category.id
    finally:
        await database.shutdown()


@pytest.fixture(params=["sqlite", "postgres"])
def storefront_setup(tmp_path: Path, request):
    postgres = request.param == "postgres"
    if postgres and not os.getenv("SCHEMA_TEST_POSTGRES_URL"):
        pytest.skip("Requires disposable PostgreSQL test database")
    url = (
        os.environ["SCHEMA_TEST_POSTGRES_URL"]
        if postgres
        else f"sqlite+aiosqlite:///{tmp_path / 'storefront.db'}"
    )
    if postgres:
        from sqlalchemy import make_url

        assert (make_url(url).database or "").startswith("test_")
        migrate(url, "upgrade", "head")
    settings = favorite_settings(url).model_copy(
        update={
            "catalog_reads_enabled": True,
            "minio_public_base_url": "https://media.example.test",
        }
    )
    products, tokens, users = asyncio.run(seed_favorites(settings, create_schema=not postgres))
    category_id = asyncio.run(seed_storefront(settings, products))

    async def cleanup():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                media_ids = list(
                    await session.scalars(
                        select(ProductMedia.media_object_id).where(
                            ProductMedia.product_id.in_(products)
                        )
                    )
                )
                category_ids = list(
                    await session.scalars(
                        select(Product.category_id).where(
                            Product.id.in_(products), Product.category_id.is_not(None)
                        )
                    )
                )
                await session.execute(delete(Product).where(Product.id.in_(products)))
                await session.execute(delete(MediaObject).where(MediaObject.id.in_(media_ids)))
                await session.execute(
                    delete(ProductCategory).where(ProductCategory.id.in_(category_ids))
                )
                await session.execute(delete(User).where(User.id.in_(users)))
                await session.commit()
        finally:
            await database.shutdown()

    try:
        with TestClient(create_app(settings=settings)) as client:
            yield client, products, category_id, tokens
    finally:
        if postgres:
            asyncio.run(cleanup())


def test_storefront_exposes_only_public_products_and_one_public_image(storefront_setup):
    client, products, category_id, _ = storefront_setup
    response = client.get(CATALOG)
    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == products[:3][::-1]
    card = payload["items"][-1]
    assert card == {
        "id": products[0],
        "title": "Футболка 100%",
        "price": "3000.50",
        "category_id": category_id,
        "category_name": "Футболки",
        "colors": ["Чёрный", "Белый"],
        "tags": ["Хлопок"],
        "source": "garment_buro",
        "image_url": "https://media.example.test/catalog/front/card.png",
        "image_alt": "Real product photo",
    }
    assert payload["next_cursor"] is None
    assert payload["items"][0]["image_url"] is None


@pytest.mark.parametrize(
    "sort,order",
    [
        ("newest", [2, 1, 0]),
        ("oldest", [0, 1, 2]),
        ("cheap", [1, 0, 2]),
        ("expensive", [2, 1, 0]),
    ],
)
def test_storefront_keyset_pages_have_stable_price_ties(storefront_setup, sort, order):
    client, products, _, _ = storefront_setup
    actual, cursor = [], None
    while True:
        params = {"limit": 1, "sort": sort}
        if cursor:
            params["cursor"] = cursor
        response = client.get(CATALOG, params=params)
        assert response.status_code == 200
        page = response.json()
        actual.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
        assert len(actual) < 4
    assert actual == [products[index] for index in order]


def test_storefront_date_sort_uses_creation_time_with_an_id_tie_break(storefront_setup):
    client, products, _, _ = storefront_setup

    async def set_dates():
        database = DatabaseManager(client.app.state.settings)
        await database.startup()
        try:
            async with database.session() as session:
                for index, product_id in enumerate(products[:3]):
                    created = datetime(2026, 1, 3 if index < 2 else 1, tzinfo=timezone.utc)
                    await session.execute(
                        update(Product).where(Product.id == product_id).values(created_at=created)
                    )
                await session.commit()
        finally:
            await database.shutdown()

    asyncio.run(set_dates())
    for sort, expected in (
        ("newest", [products[1], products[0], products[2]]),
        ("oldest", [products[2], products[0], products[1]]),
    ):
        actual, cursor = [], None
        for _ in range(3):
            page = client.get(
                CATALOG, params={"limit": 1, "sort": sort, **({"cursor": cursor} if cursor else {})}
            ).json()
            actual.extend(item["id"] for item in page["items"])
            cursor = page["next_cursor"]
        assert actual == expected
        assert cursor is None


def test_storefront_filters_search_and_bounded_batch_ids(storefront_setup):
    client, products, category_id, _ = storefront_setup

    def ids(params):
        response = client.get(CATALOG, params=params)
        assert response.status_code == 200, response.text
        return [item["id"] for item in response.json()["items"]]

    assert ids({"query": "Футболка"}) == [products[2], products[0]]
    assert ids({"query": "Хлопок"}) == [products[0]]
    assert ids({"query": "%"}) == [products[0]]
    assert ids({"query": "_"}) == [products[2]]
    assert ids({"query": "no matching products"}) == []
    assert ids({"category_ids": [category_id], "colors": ["Чёрный", "Серый"]}) == [products[0]]
    assert ids({"colors": ["Белый"], "min_price": "3000.50", "max_price": "3000.50"}) == [
        products[0]
    ]
    assert ids({"colors": ["Чёр"]}) == []
    assert ids({"source": "user"}) == [products[1]]
    assert ids({"ids": [products[0], products[3], products[4], products[5]]}) == [products[0]]


@pytest.mark.parametrize("sort", ["cheap", "expensive"])
def test_storefront_filtered_price_continuations_keep_public_policy_and_all_filters(
    storefront_setup, sort
):
    client, products, category_id, _ = storefront_setup
    cases = [
        (
            {
                "category_ids": [category_id],
                "colors": ["Белый"],
                "source": "garment_buro",
                "min_price": "3000.50",
                "max_price": "8000",
            },
            [products[0], products[2]],
        ),
        ({"query": "Футболка", "colors": ["Белый"]}, [products[0], products[2]]),
        ({"ids": products}, [products[1], products[0], products[2]]),
        ({"min_price": "3000.50", "max_price": "3000.50"}, [products[1], products[0]]),
    ]
    for filters, ascending in cases:
        # Expensive keeps id DESC inside a price tie, like cheap.
        expected = (
            [item for item in [products[2], products[1], products[0]] if item in ascending]
            if sort == "expensive"
            else ascending
        )
        actual, cursor = [], None
        while True:
            response = client.get(
                CATALOG,
                params={
                    **filters,
                    "sort": sort,
                    "limit": 1,
                    **({"cursor": cursor} if cursor else {}),
                },
            )
            assert response.status_code == 200, response.text
            page = response.json()
            actual.extend(item["id"] for item in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
            assert len(actual) <= len(expected)
        assert actual == expected


def test_storefront_rejects_unbounded_queries_and_incompatible_cursors(storefront_setup):
    client, products, _, _ = storefront_setup
    first = client.get(CATALOG, params={"limit": 1}).json()
    cursor = first["next_cursor"]
    for params in (
        {"limit": 0},
        {"limit": 101},
        {"min_price": -1},
        {"min_price": "NaN"},
        {"min_price": "1.001"},
        {"max_price": "Infinity"},
        {"min_price": 100, "max_price": 99},
        {"query": "a" * 201},
        {"source": "community"},
        {"ids": [products[0]] * 101},
        {"ids": [0]},
        {"category_ids": [0]},
        {"colors": ["a"] * 21},
        {"colors": [""]},
        {"cursor": "bad"},
        {"cursor": "x" * 1025},
        {"cursor": cursor, "query": "Худи"},
        {"cursor": cursor, "sort": "cheap"},
    ):
        assert client.get(CATALOG, params=params).status_code == 422, params


def test_storefront_options_come_from_published_products(storefront_setup):
    client, _, category_id, _ = storefront_setup
    response = client.get("/api/catalog/options")
    assert response.status_code == 200
    assert response.json() == {
        "categories": [{"id": category_id, "name": "Футболки"}],
        "colors": ["Белый", "Серый", "Чёрный"],
    }


def test_storefront_options_deduplicate_palettes_and_follow_publication_changes(storefront_setup):
    client, products, category_id, _ = storefront_setup

    async def change(stage):
        database = DatabaseManager(client.app.state.settings)
        await database.startup()
        try:
            async with database.session() as session:
                if stage == "palettes":
                    for product_id, colors in zip(
                        products[:3],
                        [["Чёрный", "Белый", "Белый"], ["Белый", "Чёрный"], []],
                        strict=True,
                    ):
                        await session.execute(
                            update(Product).where(Product.id == product_id).values(colors=colors)
                        )
                    await session.execute(
                        update(Product)
                        .where(Product.id.in_(products[3:]))
                        .values(colors=["Нельзя показывать"])
                    )
                elif stage == "hide_category":
                    await session.execute(
                        update(ProductCategory)
                        .where(ProductCategory.id == category_id)
                        .values(is_active=False)
                    )
                elif stage == "hide_last":
                    await session.execute(
                        update(Product).where(Product.id == products[1]).values(is_active=False)
                    )
                elif stage == "only_empty":
                    await session.execute(
                        update(Product).where(Product.id == products[0]).values(is_active=False)
                    )
                elif stage == "hide_all":
                    await session.execute(
                        update(Product).where(Product.id == products[2]).values(is_active=False)
                    )
                else:
                    await session.execute(
                        update(ProductCategory)
                        .where(ProductCategory.id == category_id)
                        .values(is_active=True)
                    )
                    await session.execute(
                        update(Product)
                        .where(Product.id == products[0])
                        .values(is_active=True, colors=["Новый"])
                    )
                await session.commit()
        finally:
            await database.shutdown()

    for stage, categories, colors in (
        ("palettes", [{"id": category_id, "name": "Футболки"}], ["Белый", "Чёрный"]),
        ("hide_category", [], ["Белый", "Чёрный"]),
        ("hide_last", [], []),
        ("republish", [{"id": category_id, "name": "Футболки"}], ["Новый"]),
        ("only_empty", [{"id": category_id, "name": "Футболки"}], []),
        ("hide_all", [], []),
    ):
        asyncio.run(change(stage))
        response = client.get("/api/catalog/options")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"categories": categories, "colors": colors}


@pytest.mark.parametrize("storefront_setup", ["postgres"], indirect=True)
def test_storefront_cyrillic_case_insensitive_search_on_target_postgres(storefront_setup):
    client, products, _, _ = storefront_setup
    assert [
        row["id"] for row in client.get(CATALOG, params={"query": "футболка"}).json()["items"]
    ] == products[:3:2][::-1]
    assert [
        row["id"] for row in client.get(CATALOG, params={"query": "ХлОпОк"}).json()["items"]
    ] == products[:1]


def test_storefront_page_uses_two_queries_without_variant_or_description_loading(storefront_setup):
    client, _, _, _ = storefront_setup
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if request_id_context.get() == "storefront-query-count":
            statements.append(statement.lower())

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get(
            CATALOG, params={"limit": 2}, headers={"X-Request-ID": "storefront-query-count"}
        )
        assert response.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 2
    assert "limit" in statements[0]
    assert not any("product_variants" in sql or "products.description" in sql for sql in statements)


@pytest.mark.parametrize("storefront_setup", ["postgres"], indirect=True)
def test_storefront_price_pages_use_ordered_indexes_on_target_postgres(storefront_setup):
    client, _, _, _ = storefront_setup
    settings = client.app.state.settings
    inserted = []

    async def seed():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                result = await session.execute(
                    insert(Product).returning(Product.id),
                    [
                        {
                            "title": "Plan sample",
                            "price": Decimal(index % 1000),
                            "colors": [],
                            "sizes": [],
                        }
                        for index in range(20000)
                    ],
                )
                inserted.extend(result.scalars())
                await session.execute(text("ANALYZE products"))
                await session.commit()
        finally:
            await database.shutdown()

    async def explain(statement, parameters):
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.connect() as connection:
                result = await connection.exec_driver_sql(
                    "EXPLAIN (FORMAT JSON) " + statement, parameters
                )
                return result.scalar_one()[0]["Plan"]
        finally:
            await database.shutdown()

    async def cleanup():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                await session.execute(delete(Product).where(Product.id.in_(inserted)))
                await session.commit()
        finally:
            await database.shutdown()

    asyncio.run(seed())
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if request_id_context.get() == "storefront-query-plan":
            statements.append((statement, parameters))

    engine = client.app.state.database.engine.sync_engine
    try:
        for sort, index_name in (
            ("cheap", "ix_products_public_price_cheap"),
            ("expensive", "ix_products_public_price_expensive"),
            ("newest", "ix_products_public_recent"),
            ("oldest", "ix_products_public_recent"),
        ):
            statements.clear()
            event.listen(engine, "before_cursor_execute", capture)
            try:
                assert (
                    client.get(
                        CATALOG,
                        params={"sort": sort, "limit": 24},
                        headers={"X-Request-ID": "storefront-query-plan"},
                    ).status_code
                    == 200
                )
            finally:
                event.remove(engine, "before_cursor_execute", capture)
            plan = json.dumps(asyncio.run(explain(*statements[0])))
            assert index_name in plan, plan
            assert '"Node Type": "Sort"' not in plan, plan
    finally:
        asyncio.run(cleanup())


def test_favorite_status_is_account_scoped_and_bounded_to_visible_cards(storefront_setup):
    client, products, _, (owner, other) = storefront_setup
    path = "/api/profile/favorites/status"
    assert client.get(path, params={"product_ids": products[:3]}).status_code == 401
    assert client.put(f"/api/profile/favorites/{products[0]}", headers=owner).status_code == 204
    for account, expected in ((owner, [products[0]]), (other, [])):
        response = client.get(path, params={"product_ids": products[:3]}, headers=account)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"product_ids": expected}
    for params in ({}, {"product_ids": [0]}, {"product_ids": products[:1] * 101}):
        assert client.get(path, params=params, headers=owner).status_code == 422
