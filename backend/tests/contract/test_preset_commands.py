"""Commands reject invalid work early and delete large legacy sources by cursor."""

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, event, func, insert, select, update

from app.modules.catalog.deletion_audit import catalog_deletion_audit
from app.modules.catalog.models import CatalogAuditEvent, Product, ProductVariant
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.router import write_router
from app.modules.catalog.schemas import ProductWriteRequest
from app.modules.catalog.service import CatalogProductVersionConflictError, CatalogWriteService
from app.modules.media.models import MediaObject, ProductMedia, ProductVariantMedia
from app.modules.partners.models import PartnerLanding, PartnerLandingProduct, PartnerProfile
from tests.contract.test_preset_editor_source import preset_source as preset_source
from tests.contract.test_reference_directory import ROOT
from tests.contract.test_reference_directory import references as references


@pytest.fixture
def command_source(preset_source):
    client, product, empty, variant, tokens, prefix = preset_source
    client.app.include_router(write_router)
    client.app.state.settings = client.app.state.settings.model_copy(
        update={"catalog_writes_enabled": True}
    )

    async def unreserve():
        if client.app.state.database.engine.dialect.name == "sqlite":
            # This lightweight test dialect must enforce PostgreSQL's FK/cascade semantics.
            def foreign_keys(connection, record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

            event.listen(client.app.state.database.engine.sync_engine, "connect", foreign_keys)
            await client.app.state.database.engine.dispose()
        async with client.app.state.database.session() as session:
            await session.execute(
                update(Product).where(Product.id == product).values(reserved_quantity=0)
            )
            await session.execute(
                update(ProductVariant)
                .where(ProductVariant.product_id == product)
                .values(reserved_quantity=0)
            )
            await session.execute(
                update(MediaObject)
                .where(MediaObject.object_key.startswith(f"uploads/{prefix}-"))
                .values(bucket_name=client.app.state.settings.minio_media_bucket)
            )
            await session.commit()

    client.portal.call(unreserve)
    body = client.get(f"{ROOT}/products/{product}").json()
    body.update(expected_version=1, title="Updated preset")
    try:
        yield client, product, empty, variant, tokens, prefix, body
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(
                    delete(CatalogAuditEvent).where(
                        CatalogAuditEvent.product_id.in_([product, empty])
                    )
                )
                await session.commit()

        client.portal.call(cleanup)


def test_stale_command_checks_fresh_parent_before_any_children(command_source):
    client, product, _, _, _, _, body = command_source

    async def scenario():
        async with client.app.state.database.session() as session:
            cached = await CatalogRepository().get_product(session, product)
            await session.execute(
                update(Product).where(Product.id == product).values(version=2),
                execution_options={"synchronize_session": False},
            )
            assert cached.version == 1
            statements = []

            def capture(conn, cursor, sql, params, context, many):
                if sql.lstrip().upper().startswith("SELECT"):
                    statements.append(sql)

            engine = client.app.state.database.engine.sync_engine
            event.listen(engine, "before_cursor_execute", capture)
            try:
                with pytest.raises(CatalogProductVersionConflictError):
                    await CatalogWriteService(client.app.state.settings).update_product(
                        session,
                        product_id=product,
                        expected_version=1,
                        payload=ProductWriteRequest.model_validate(body),
                        actor_user_id=None,
                    )
                assert (
                    len(statements) == 1
                    and "product_variants" not in statements[0]
                    and "media" not in statements[0]
                )
                assert cached.version == 2
            finally:
                event.remove(engine, "before_cursor_execute", capture)
                await session.rollback()

    client.portal.call(scenario)


@pytest.mark.parametrize("extra", [1, 19800])
def test_oversized_put_is_atomic_before_media_and_delete_checks_last_reserved_sku(
    command_source, extra
):
    client, product, _, _, tokens, prefix, body = command_source

    async def seed():
        async with client.app.state.database.session() as session:
            await session.execute(
                insert(ProductVariant),
                [
                    {"product_id": product, "sku": f"{prefix}-extra-{i}", "stock_quantity": 7}
                    for i in range(extra)
                ],
            )
            last = await session.scalar(
                select(func.max(ProductVariant.id)).where(ProductVariant.product_id == product)
            )
            await session.execute(
                update(ProductVariant).where(ProductVariant.id == last).values(reserved_quantity=1)
            )
            await session.commit()
            return last

    last = client.portal.call(seed)
    statements = []

    def capture(conn, cursor, sql, params, context, many):
        statements.append(sql)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        for path, headers in [
            (f"{ROOT}/products/{product}", {}),
            (f"/api/products/{product}", tokens[0]),
        ]:
            response = client.put(path, headers=headers, json=body)
            assert response.status_code == 409, response.text
            assert response.json()["detail"]["code"] == "catalog_editor_variant_limit"
            assert response.headers["cache-control"] == "no-store"
            reserved = client.delete(path, headers=headers)
            assert reserved.status_code == 409, reserved.text
        assert not any(
            table in sql.lower()
            for sql in statements
            for table in ["from product_media", "from product_variant_media", "from media_objects"]
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    async def verify():
        async with client.app.state.database.session() as session:
            persisted = await session.get(Product, product)
            assert persisted.version == 1 and persisted.title == f"{prefix} source"
            assert (await session.get(ProductVariant, last)).reserved_quantity == 1
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProductVariant)
                    .where(ProductVariant.product_id == product)
                )
                == 200 + extra
            )
            assert not list(
                await session.scalars(
                    select(CatalogAuditEvent).where(CatalogAuditEvent.product_id == product)
                )
            )

    client.portal.call(verify)


def test_put_200_keeps_complete_source_and_rejects_stale_repeat(command_source):
    client, product, _, _, tokens, prefix, body = command_source
    body["variants"].reverse()
    response = client.put(f"{ROOT}/products/{product}", json=body)
    assert response.status_code == 200, response.text
    after = client.get(f"/api/products/{product}", headers=tokens[0]).json()
    assert after["version"] == 2 and after["title"] == "Updated preset"
    assert len(after["variants"]) == 200
    assert [row["sku"] for row in after["variants"]] == [f"{prefix}-{i}" for i in range(200)]
    assert all(
        row["stock_quantity"] == 7 and row["reserved_quantity"] == 0 for row in after["variants"]
    )
    assert after["variants"][0]["width_cm"] == 64.25 and after["variants"][0]["height_cm"] == 72.35
    assert after["gallery_images"] == body["gallery_images"]
    stale = client.put(f"/api/products/{product}", headers=tokens[0], json=body)
    assert (
        stale.status_code == 409
        and stale.json()["detail"]["code"] == "catalog_product_version_conflict"
    )


def test_deletion_checksum_matches_versioned_stored_rows_and_covers_hidden_media(command_source):
    client, product_id, _, variant_id, _, prefix, _ = command_source

    def default(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return (
                value.replace(tzinfo=value.tzinfo or timezone.utc)
                .astimezone(timezone.utc)
                .isoformat(timespec="microseconds")
            )
        raise TypeError(type(value))

    async def scenario():
        async with client.app.state.database.session() as session:
            product = await CatalogRepository().get_product_for_update(session, product_id)
            product_row = dict(
                (
                    await session.execute(
                        select(*Product.__table__.columns).where(Product.id == product_id)
                    )
                )
                .mappings()
                .one()
            )
            media = [
                column.label("media_" + column.name) for column in MediaObject.__table__.columns
            ]
            source = {"schema": "catalog.product-deleted.v2", "product": product_row}
            queries = {
                "variants": select(*ProductVariant.__table__.columns)
                .where(ProductVariant.product_id == product_id)
                .order_by(ProductVariant.id),
                "product_media": select(*ProductMedia.__table__.columns, *media)
                .join(MediaObject, MediaObject.id == ProductMedia.media_object_id)
                .where(ProductMedia.product_id == product_id)
                .order_by(ProductMedia.id),
                "variant_media": select(*ProductVariantMedia.__table__.columns, *media)
                .join(MediaObject, MediaObject.id == ProductVariantMedia.media_object_id)
                .join(ProductVariant, ProductVariant.id == ProductVariantMedia.product_variant_id)
                .where(ProductVariant.product_id == product_id)
                .order_by(ProductVariantMedia.product_variant_id, ProductVariantMedia.id),
            }
            for name, statement in queries.items():
                source[name] = [dict(row) for row in (await session.execute(statement)).mappings()]
            reference = hashlib.sha256(
                json.dumps(
                    source,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=default,
                ).encode()
            ).hexdigest()
            evidence = await catalog_deletion_audit(session, product)
            assert evidence.checksum == reference
            assert evidence.variants_count == 200 and evidence.media_links_count == 29
            assert evidence.media_references_count == 21
            assert len(session.identity_map) == 1
            async with session.begin_nested() as change:
                await session.execute(
                    update(ProductVariant)
                    .where(ProductVariant.id == variant_id)
                    .values(sku=f"{prefix}-changed", width_cm=Decimal("66.75"))
                )
                assert (await catalog_deletion_audit(session, product)).checksum != reference
                await change.rollback()
            async with session.begin_nested() as change:
                await session.execute(
                    update(MediaObject)
                    .where(MediaObject.object_key == f"uploads/{prefix}-4.webp")
                    .values(size_bytes=11)
                )
                assert (await catalog_deletion_audit(session, product)).checksum != reference
                await change.rollback()
            assert (await catalog_deletion_audit(session, product)).checksum == reference
            await session.rollback()

    client.portal.call(scenario)


def test_delete_20000_skus_streams_256_rows_and_preserves_shared_objects(
    command_source, monkeypatch
):
    client, product_id, empty_id, variant_id, _, prefix, _ = command_source

    async def scenario():
        async with client.app.state.database.session() as session:
            await session.execute(
                insert(ProductVariant),
                [{"product_id": product_id, "sku": f"{prefix}-large-{i}"} for i in range(19800)],
            )
            media_id = await session.scalar(
                select(MediaObject.id).where(MediaObject.object_key == f"uploads/{prefix}-0.webp")
            )
            session.add(
                ProductMedia(product_id=empty_id, media_object_id=media_id, role="image_left")
            )
            await session.execute(
                insert(ProductMedia),
                [
                    {
                        "product_id": product_id,
                        "media_object_id": media_id,
                        "role": "gallery_images",
                        "sort_order": i + 100,
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
                        "sort_order": i + 100,
                    }
                    for i in range(6000)
                ],
            )
            await session.commit()
        batches, peaks, statements = [], [], []
        async with client.app.state.database.session() as session:
            original = session.stream

            class Mappings:
                def __init__(self, result):
                    self.result = result

                async def partitions(self, size):
                    assert size == 256
                    async for batch in self.result.mappings().partitions(size):
                        batches.append(len(batch))
                        peaks.append(len(session.identity_map))
                        yield batch

            class Result:
                def __init__(self, result):
                    self.result = result

                def mappings(self):
                    return Mappings(self.result)

                async def close(self):
                    await self.result.close()

            async def stream(statement):
                assert statement.get_execution_options()["yield_per"] == 256
                return Result(await original(statement))

            monkeypatch.setattr(session, "stream", stream)

            def capture(conn, cursor, sql, params, context, many):
                statements.append(sql)

            engine = client.app.state.database.engine.sync_engine
            event.listen(engine, "before_cursor_execute", capture)
            try:
                await CatalogWriteService(client.app.state.settings).delete_product(
                    session, product_id=product_id, actor_user_id=None
                )
                await session.commit()
            finally:
                event.remove(engine, "before_cursor_execute", capture)
            assert max(batches) == 256 and sum(batches) == 32029
            assert max(peaks) == 1
            selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
            assert len(selects) == 6  # Parent lock, two reservation checks, three scalar streams.
            assert not any("WHERE product_variants.product_id IN" in sql for sql in selects)
            assert await session.get(Product, product_id) is None
            audit = await session.scalar(
                select(CatalogAuditEvent).where(CatalogAuditEvent.product_id == product_id)
            )
            assert audit.details == {
                "snapshot_schema": "catalog.product-deleted.v2",
                "variants_count": 20000,
                "media_links_count": 12029,
                "media_references_count": 12021,
            }
            assert len(audit.snapshot_checksum_sha256) == 64
            assert await session.get(MediaObject, media_id) is not None
            assert (
                await session.scalar(
                    select(ProductMedia.media_object_id).where(ProductMedia.product_id == empty_id)
                )
                == media_id
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProductVariant)
                    .where(ProductVariant.product_id == product_id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProductMedia)
                    .where(ProductMedia.product_id == product_id)
                )
                == 0
            )

    client.portal.call(scenario)


def test_linked_landing_rejects_delete_and_rolls_back_children_and_audit(
    command_source, references
):
    client, product_id, _, _, _, prefix, _ = command_source

    async def seed():
        async with client.app.state.database.session() as session:
            owner = PartnerProfile(
                user_id=references[5][0], code=prefix, display_name="Owner", commission_bps=1000
            )
            session.add(owner)
            await session.flush()
            landing = PartnerLanding(
                partner_id=owner.id,
                slug=prefix,
                title="Linked",
                headline="Collection",
                description="Description",
                cta_label="Open",
                cta_href="/",
                content={},
            )
            session.add(landing)
            await session.flush()
            session.add(
                PartnerLandingProduct(landing_id=landing.id, product_id=product_id, position=0)
            )
            await session.commit()
            return owner.id, landing.id

    owner_id, landing_id = client.portal.call(seed)
    try:
        response = client.delete(f"{ROOT}/products/{product_id}")
        assert response.status_code == 409, response.text

        async def verify():
            async with client.app.state.database.session() as session:
                assert await session.get(Product, product_id) is not None
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(ProductVariant)
                        .where(ProductVariant.product_id == product_id)
                    )
                    == 200
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(ProductMedia)
                        .where(ProductMedia.product_id == product_id)
                    )
                    == 19
                )
                assert not list(
                    await session.scalars(
                        select(CatalogAuditEvent).where(CatalogAuditEvent.product_id == product_id)
                    )
                )

        client.portal.call(verify)
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(delete(PartnerLanding).where(PartnerLanding.id == landing_id))
                await session.execute(delete(PartnerProfile).where(PartnerProfile.id == owner_id))
                await session.commit()

        client.portal.call(cleanup)


@pytest.mark.parametrize("identity", ["duplicate", "foreign"])
def test_invalid_variant_identity_rejects_before_media(command_source, identity):
    client, product, _, _, tokens, _, body = command_source
    body["variants"][-1]["id"] = (
        body["variants"][0]["id"] if identity == "duplicate" else 2147483647
    )
    statements = []

    def capture(conn, cursor, sql, params, context, many):
        statements.append(sql)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        for path, headers, status in [
            (f"{ROOT}/products/{product}", {}, 409),
            (f"/api/products/{product}", tokens[0], 422),
        ]:
            response = client.put(path, headers=headers, json=body)
            assert response.status_code == status, response.text
        assert not any(
            table in sql.lower()
            for sql in statements
            for table in ["from product_media", "from product_variant_media", "from media_objects"]
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    async def verify():
        async with client.app.state.database.session() as session:
            assert (await session.get(Product, product)).version == 1
            assert not list(
                await session.scalars(
                    select(CatalogAuditEvent).where(CatalogAuditEvent.product_id == product)
                )
            )

    client.portal.call(verify)
