"""Complete editor media is paged and bounded by its existing write contract."""

import math

import pytest
from sqlalchemy import delete, event, func, insert, select, update

from app.modules.catalog.admin_service import CatalogAdminReadService
from app.modules.catalog.editor_media import (
    PRODUCT_MEDIA_FIELD_LIMITS,
    CatalogEditorMediaLimitError,
)
from app.modules.catalog.editor_repository import CatalogEditorRepository
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.repository import CatalogRepository
from app.modules.media.models import MediaObject, ProductMedia, ProductVariantMedia
from tests.contract.test_preset_commands import command_source as command_source
from tests.contract.test_preset_editor_source import preset_source as preset_source
from tests.contract.test_reference_directory import ROOT
from tests.contract.test_reference_directory import references as references


@pytest.mark.parametrize("kind", ["product", "variant"])
@pytest.mark.parametrize("extra", [0, 1])
def test_full_csv_boundary_round_trips_or_rejects_without_truncation(command_source, kind, extra):
    client, product, empty, variant, tokens, prefix, _ = command_source
    target = empty if kind == "product" else product
    model = ProductMedia if kind == "product" else ProductVariantMedia
    owner = model.product_id if kind == "product" else model.product_variant_id
    owner_id = target if kind == "product" else variant
    role = "gallery_images" if kind == "product" else "images"
    url = f"/uploads/{prefix}-я.webp"
    count = (32768 + 1) // (len(url) + 1)
    remainder = 32768 - (count * (len(url) + 1) - 1)
    last = url + "x" * (remainder + extra)
    expected = ",".join([url] * (count - 1) + [last])
    assert len(expected) == 32768 + extra and len(expected.encode()) > len(expected)

    async def seed():
        async with client.app.state.database.session() as session:
            ids = list(
                await session.scalars(
                    select(MediaObject.id)
                    .where(
                        MediaObject.object_key.in_(
                            [f"uploads/{prefix}-0.webp", f"uploads/{prefix}-1.webp"]
                        )
                    )
                    .order_by(MediaObject.id)
                )
            )
            for media_id, value in zip(ids, [url, last], strict=True):
                await session.execute(
                    update(MediaObject)
                    .where(MediaObject.id == media_id)
                    .values(object_key=value[1:])
                )
            await session.execute(delete(model).where(owner == owner_id, model.role == role))
            await session.execute(
                insert(model),
                [
                    {
                        owner.key: owner_id,
                        "media_object_id": ids[0] if i < count - 1 else ids[1],
                        "role": role,
                        "sort_order": i,
                    }
                    for i in range(count)
                ],
            )
            await session.commit()

    client.portal.call(seed)
    for path, headers in [
        (f"{ROOT}/products/{target}", {}),
        (f"/api/products/{target}", tokens[0]),
    ]:
        response = client.get(path, headers=headers)
        assert response.status_code == (409 if extra else 200), response.text
        assert response.headers["cache-control"] == "no-store"
        if extra:
            assert response.json()["detail"]["code"] == "catalog_editor_media_limit"
            assert "variants" not in response.json()
        else:
            source = response.json()
            actual = source[role] if kind == "product" else source["variants"][0][role]
            assert actual == expected
    if not extra:
        # The same source must be accepted by the existing write schema and survive PUT.
        source["expected_version"] = source["version"]
        saved = client.put(f"/api/products/{target}", headers=tokens[0], json=source)
        assert saved.status_code == 200, saved.text
        value = saved.json()[role] if kind == "product" else saved.json()["variants"][0][role]
        assert value == expected and saved.json()["version"] == 2

    async def verify():
        async with client.app.state.database.session() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(owner == owner_id, model.role == role)
                )
                == count
            )
            assert (await session.get(Product, target)).version == (1 if extra else 2)

    client.portal.call(verify)


@pytest.mark.parametrize(
    "kind,state",
    [
        ("product", "ready"),
        ("variant", "ready"),
        ("product", "private"),
        ("variant", "pending"),
        ("unknown", "ready"),
    ],
)
def test_20000_media_links_stop_early_with_bounded_scalar_pages(
    command_source, monkeypatch, kind, state
):
    client, product, _, variant, tokens, prefix, _ = command_source
    is_variant = kind == "variant"
    model = ProductVariantMedia if is_variant else ProductMedia
    owner = model.product_variant_id if is_variant else model.product_id
    owner_id = variant if is_variant else product
    role = (
        "images"
        if is_variant
        else ("unknown-legacy-role" if kind == "unknown" else "gallery_images")
    )
    url = f"/uploads/{prefix}-0.webp"

    async def seed():
        async with client.app.state.database.session() as session:
            media = await session.scalar(
                select(MediaObject.id).where(MediaObject.object_key == url[1:])
            )
            await session.execute(delete(ProductMedia).where(ProductMedia.product_id == product))
            await session.execute(
                delete(ProductVariantMedia).where(ProductVariantMedia.product_variant_id == variant)
            )
            await session.execute(
                update(MediaObject)
                .where(MediaObject.id == media)
                .values(
                    is_public=state != "private",
                    status="pending" if state == "pending" else "ready",
                )
            )
            await session.execute(
                insert(model),
                [
                    {owner.key: owner_id, "media_object_id": media, "role": role, "sort_order": i}
                    for i in range(20000)
                ],
            )
            await session.commit()

    client.portal.call(seed)
    pages, loaded = [], []
    original = CatalogEditorRepository.media_page

    async def track(cls, *args, **kwargs):
        page = await original(*args, **kwargs)
        pages.append(len(page))
        return page

    monkeypatch.setattr(CatalogEditorRepository, "media_page", classmethod(track))

    async def scenario():
        async with client.app.state.database.session() as session:

            def load(sync_session, row):
                if isinstance(row, (MediaObject, ProductMedia, ProductVariantMedia)):
                    loaded.append(row)

            event.listen(session.sync_session, "loaded_as_persistent", load)
            try:
                with pytest.raises(CatalogEditorMediaLimitError):
                    await CatalogAdminReadService(
                        CatalogResponseMapper(client.app.state.settings)
                    ).detail(session, product)
            finally:
                event.remove(session.sync_session, "loaded_as_persistent", load)
            assert not loaded and not session.new and not session.dirty and not session.deleted
            assert max(pages) <= 257
            budget = (
                sum(value + 1 for value in PRODUCT_MEDIA_FIELD_LIMITS.values())
                if kind == "unknown"
                else 32768
            )
            crossing_row = (budget + 1) // (len(url) + 1) + 1
            # One row of lookahead per page; the rest of the 20k source is never fetched.
            assert sum(pages) <= math.ceil(crossing_row / 256) * 257
            assert sum(pages) < 20000
            assert (
                await session.scalar(
                    select(func.count()).select_from(model).where(owner == owner_id)
                )
                == 20000
            )
            assert (await session.get(Product, product)).version == 1
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProductVariant)
                    .where(ProductVariant.product_id == product)
                )
                == 200
            )

    client.portal.call(scenario)
    for path, headers in [
        (f"{ROOT}/products/{product}", {}),
        (f"/api/products/{product}", tokens[0]),
    ]:
        response = client.get(path, headers=headers)
        assert response.status_code == 409 and response.headers["cache-control"] == "no-store"
        assert response.json()["detail"]["code"] == "catalog_editor_media_limit"
    customer = client.get(f"/api/products/{product}", headers=tokens[1])
    assert customer.status_code == 403


def test_scalar_source_reads_fresh_media_without_reusing_cached_orm_records(command_source):
    client, product_id, _, _, _, prefix, _ = command_source

    async def scenario():
        async with client.app.state.database.session() as session:
            cached = await CatalogRepository().get_product(session, product_id)
            media = cached.media_links[0].media
            await session.execute(
                update(MediaObject).where(MediaObject.id == media.id).values(is_public=False),
                execution_options={"synchronize_session": False},
            )
            assert media.is_public
            source = await CatalogAdminReadService(
                CatalogResponseMapper(client.app.state.settings)
            ).detail(session, product_id)
            assert source.image_left is None
            assert source.gallery_images == ",".join(f"/uploads/{prefix}-{i}.webp" for i in [1, 2])
            assert (
                media.is_public
            )  # Source projections do not mutate another reader's cached object.
            await session.rollback()

    client.portal.call(scenario)
