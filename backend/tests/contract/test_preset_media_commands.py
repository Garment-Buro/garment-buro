"""Replacement reads only submitted/final media and remains atomic on both databases."""

from decimal import Decimal

import pytest
from sqlalchemy import event, func, insert, inspect, select, update
from sqlalchemy.exc import IntegrityError

from app.modules.catalog.deletion_audit import catalog_deletion_audit
from app.modules.catalog.editor_repository import CatalogEditorRepository
from app.modules.catalog.models import CatalogAuditEvent, Product, ProductVariant
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import ProductWriteRequest
from app.modules.catalog.service import CatalogWriteService, UnknownCatalogMediaError
from app.modules.media.models import (
    MediaObject,
    ProductMedia,
    ProductMediaRole,
    ProductVariantMedia,
)
from tests.contract.test_preset_commands import command_source as command_source
from tests.contract.test_preset_editor_source import preset_source as preset_source
from tests.contract.test_reference_directory import references as references


def clear_media_fields(body):
    for role in ProductMediaRole:
        body[role.value] = None
    for variant in body["variants"]:
        variant.update(preview_image=None, images=None)


@pytest.mark.parametrize("warm", [False, True])
def test_replace_12029_old_links_reads_only_eight_new_links_and_keeps_skus(
    command_source, warm, monkeypatch
):
    client, product_id, _, variant_id, _, prefix, body = command_source
    clear_media_fields(body)
    urls = [f"/uploads/{prefix}-{i}.webp" for i in range(3)]
    body.update(
        gallery_images=",".join([urls[2], urls[0], urls[2]]),
        image_left=",".join([urls[1], urls[2]]),
        stock_quantity=999,
    )
    body.pop("tags")
    body.pop("preset_source")
    omitted = body["variants"].pop()
    body["variants"][0].update(
        images=",".join([urls[1], urls[2], urls[1]]),
        preview_image=",".join([urls[2], urls[0]]),
        width_cm="65.50",
        height_cm="78.25",
        stock_quantity=999,
    )
    body["variants"].append({**omitted, "id": None, "color": "white", "stock_quantity": 999})
    body["variants"].reverse()

    async def scenario():
        async with client.app.state.database.session() as session:
            media_id = await session.scalar(
                select(MediaObject.id).where(MediaObject.object_key == f"uploads/{prefix}-0.webp")
            )
            await session.execute(
                insert(ProductMedia),
                [
                    {
                        "product_id": product_id,
                        "media_object_id": media_id,
                        "role": "gallery_images",
                        "sort_order": 100 + i,
                    }
                    for i in range(6000)
                ],
            )
            await session.execute(
                insert(ProductVariantMedia),
                [
                    {
                        "product_variant_id": variant_id,
                        "media_object_id": media_id,
                        "role": "images",
                        "sort_order": 100 + i,
                    }
                    for i in range(6000)
                ],
            )
            await session.commit()
        async with client.app.state.database.session() as session:
            previous = None
            old_links = []
            media = None
            if warm:
                previous = await CatalogRepository().get_product(session, product_id)
                old_links = [
                    *previous.media_links,
                    *(link for variant in previous.variants for link in variant.media_links),
                ]
                media = old_links[0].media
                await session.refresh(media, ["product_links", "variant_links"])
                assert len(old_links) == 12029
            statements, hydrated, projected = [], [], []
            read_links = CatalogEditorRepository.media_links

            async def track(cls, *args, **kwargs):
                async for link in read_links(*args, **kwargs):
                    projected.append(link)
                    yield link

            monkeypatch.setattr(CatalogEditorRepository, "media_links", classmethod(track))

            def capture(conn, cursor, sql, params, context, many):
                statements.append(sql)

            def loaded(sync_session, row):
                if isinstance(row, (ProductMedia, ProductVariantMedia)):
                    hydrated.append(row)

            engine = client.app.state.database.engine.sync_engine
            event.listen(engine, "before_cursor_execute", capture)
            event.listen(session.sync_session, "loaded_as_persistent", loaded)
            try:
                result = await CatalogWriteService(client.app.state.settings).update_product(
                    session,
                    product_id=product_id,
                    expected_version=1,
                    payload=ProductWriteRequest.model_validate(body),
                    actor_user_id=None,
                )
            finally:
                event.remove(engine, "before_cursor_execute", capture)
                event.remove(session.sync_session, "loaded_as_persistent", loaded)
            first_delete = next(
                i for i, sql in enumerate(statements) if sql.startswith("DELETE FROM product_media")
            )
            assert not any(
                table in sql
                for sql in statements[:first_delete]
                for table in ("FROM product_media", "FROM product_variant_media")
            )
            assert not hydrated and len(projected) == 8
            assert result.gallery_images == body["gallery_images"]
            assert result.image_left == urls[1]
            assert result.variants[0].preview_image == urls[2]
            assert result.variants[0].images == ",".join([urls[1], urls[2], urls[1]])
            assert result.version == 2 and len(result.variants) == 200
            parent = await session.get(Product, product_id)
            assert parent.stock_quantity == 17 and parent.tags == ["аниме"]
            assert parent.preset_source == "user"
            assert {"variants", "media_links"} <= inspect(parent).unloaded
            variants = list(
                await session.scalars(
                    select(ProductVariant)
                    .where(ProductVariant.product_id == product_id)
                    .order_by(ProductVariant.id)
                )
            )
            assert [row.sku for row in variants[:-1]] == [f"{prefix}-{i}" for i in range(199)]
            assert all(row.stock_quantity == 7 for row in variants[:-1])
            assert variants[-1].sku is None and variants[-1].stock_quantity == 0
            assert variants[0].width_cm == Decimal("65.50")
            assert variants[0].height_cm == Decimal("78.25")
            # SQLite can reuse the omitted maximum ID; SKU identity still must be removed.
            assert not await session.scalar(
                select(ProductVariant.id).where(ProductVariant.sku == omitted["sku"])
            )
            assert all("media_links" in inspect(row).unloaded for row in variants)
            if warm:
                assert previous is parent and all(inspect(link).detached for link in old_links)
                assert {"product_links", "variant_links"} <= inspect(media).unloaded
            assert (
                len(
                    list(
                        await session.scalars(
                            select(CatalogAuditEvent).where(
                                CatalogAuditEvent.product_id == product_id
                            )
                        )
                    )
                )
                == 1
            )
            await session.commit()
        async with client.app.state.database.session() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProductMedia)
                    .where(ProductMedia.product_id == product_id)
                )
                == 4
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProductVariantMedia)
                    .join(ProductVariant)
                    .where(ProductVariant.product_id == product_id)
                )
                == 4
            )

    client.portal.call(scenario)


def test_empty_replacement_removes_all_owned_links_and_variants(command_source):
    client, product_id, _, _, _, _, body = command_source
    clear_media_fields(body)
    body.update(variants=[], garment_model_id=None, stock_quantity=9)

    async def scenario():
        async with client.app.state.database.session() as session:
            result = await CatalogWriteService(client.app.state.settings).update_product(
                session,
                product_id=product_id,
                expected_version=1,
                payload=ProductWriteRequest.model_validate(body),
                actor_user_id=None,
            )
            assert result.variants == [] and result.media_assets == []
            assert result.gallery_images is None and result.stock_quantity == 9
            assert not list(
                await session.scalars(
                    select(ProductVariant.id).where(ProductVariant.product_id == product_id)
                )
            )
            assert not list(
                await session.scalars(
                    select(ProductMedia.id).where(ProductMedia.product_id == product_id)
                )
            )
            await session.commit()

    client.portal.call(scenario)


def test_submitted_media_inserts_use_bounded_batches_and_preserve_duplicates(command_source):
    client, product_id, _, _, _, prefix, body = command_source
    clear_media_fields(body)
    body["variants"] = body["variants"][:1]
    urls = ",".join([f"/uploads/{prefix}-1.webp"] * 600)
    body["gallery_images"] = body["variants"][0]["images"] = urls

    async def scenario():
        async with client.app.state.database.session() as session:
            batches = []

            def capture(conn, cursor, sql, params, context, many):
                if sql.startswith(
                    ("INSERT INTO product_media ", "INSERT INTO product_variant_media ")
                ):
                    batches.append(len(context.compiled_parameters))

            engine = client.app.state.database.engine.sync_engine
            event.listen(engine, "before_cursor_execute", capture)
            try:
                result = await CatalogWriteService(client.app.state.settings).update_product(
                    session,
                    product_id=product_id,
                    expected_version=1,
                    payload=ProductWriteRequest.model_validate(body),
                    actor_user_id=None,
                )
            finally:
                event.remove(engine, "before_cursor_execute", capture)
            assert batches == [256, 256, 88, 256, 256, 88]
            assert result.gallery_images == urls and result.variants[0].images == urls
            assert len(result.media_assets) == 600
            assert list(
                await session.scalars(
                    select(ProductVariantMedia.sort_order)
                    .where(ProductVariantMedia.product_variant_id == result.variants[0].id)
                    .order_by(ProductVariantMedia.sort_order)
                )
            ) == list(range(600))
            await session.commit()

    client.portal.call(scenario)


@pytest.mark.parametrize("failure", ["validation", "after_audit", "database"])
def test_failed_replacement_preserves_complete_stored_snapshot(
    command_source, monkeypatch, failure
):
    client, product_id, empty_id, _, _, prefix, body = command_source

    async def scenario():
        if failure == "database":
            async with client.app.state.database.session() as session:
                await session.execute(
                    update(Product).where(Product.id == empty_id).values(slug=f"{prefix}-taken")
                )
                await session.commit()
        async with client.app.state.database.session() as session:
            parent = await CatalogRepository().get_product_for_update(session, product_id)
            before = await catalog_deletion_audit(session, parent)
            service = CatalogWriteService(client.app.state.settings)
            clear_media_fields(body)
            body["variants"] = body["variants"][:1]
            statements = []

            def capture(conn, cursor, sql, params, context, many):
                statements.append(sql)

            if failure == "validation":
                body["gallery_images"] = "/uploads/missing-presets-media.webp"
                error = UnknownCatalogMediaError
            elif failure == "database":
                body["slug"] = f"{prefix}-taken"
                error = IntegrityError
            else:
                audit = service._audit

                async def fail_after_audit(*args, **kwargs):
                    await audit(*args, **kwargs)
                    raise RuntimeError("Injected failure after deleting links and recording audit")

                monkeypatch.setattr(service, "_audit", fail_after_audit)
                error = RuntimeError
            engine = client.app.state.database.engine.sync_engine
            event.listen(engine, "before_cursor_execute", capture)
            try:
                with pytest.raises(error):
                    await service.update_product(
                        session,
                        product_id=product_id,
                        expected_version=1,
                        payload=ProductWriteRequest.model_validate(body),
                        actor_user_id=None,
                    )
            finally:
                event.remove(engine, "before_cursor_execute", capture)
            deletes = [sql for sql in statements if sql.startswith("DELETE")]
            assert bool(deletes) == (failure != "validation")
            await session.rollback()
        async with client.app.state.database.session() as session:
            parent = await CatalogRepository().get_product_for_update(session, product_id)
            after = await catalog_deletion_audit(session, parent)
            assert after == before
            assert parent.version == 1
            assert not list(
                await session.scalars(
                    select(CatalogAuditEvent).where(CatalogAuditEvent.product_id == product_id)
                )
            )

    client.portal.call(scenario)
