from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.carts.models import Cart
from app.modules.customer_projects.lifecycle_repository import has_references
from app.modules.design_assets.models import CartDesignAsset, DesignAsset, OrderDesignAsset
from app.modules.design_assets.repository import DesignAssetRepository
from app.modules.design_assets.security import (
    DesignAssetUnavailableError,
    digest_design_asset_token,
)
from app.modules.media.models import MediaObject
from app.modules.orders.models import Order
from tests.integration.test_cart_revisions_postgres import cart_database as cart_database
from tests.postgres_schema import migrate

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)
BUCKET = "test-private-designs"
pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


async def seed(session, *, expiry=NOW + timedelta(days=7)):
    media = MediaObject(
        bucket_name=BUCKET,
        object_key=f"designs/{uuid4().hex}.webp",
        content_type="image/webp",
        size_bytes=123456,
        checksum_sha256="a" * 64,
        is_public=False,
        status="ready",
    )
    session.add(media)
    await session.flush()
    token = uuid4().hex + uuid4().hex[:11]
    asset = DesignAsset(
        media_object_id=media.id,
        access_digest_sha256=digest_design_asset_token(token),
        expires_at=expiry,
    )
    session.add(asset)
    await session.flush()
    return token, asset, media


def test_retention_is_real_fk_and_expired_unattached_assets_are_pruned_in_bounded_batches(
    cart_database,
):
    async def scenario():
        engine = create_async_engine(cart_database)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repo = DesignAssetRepository()
        try:
            async with sessions() as session:
                token, asset, media = await seed(session)
                cart = Cart(
                    token_digest_sha256=uuid4().hex * 2, expires_at=NOW + timedelta(days=30)
                )
                order = Order(
                    items_subtotal=0,
                    delivery_price=0,
                    total_price=0,
                    request_fingerprint_sha256="b" * 64,
                )
                session.add_all([cart, order])
                await session.flush()
                assets = await repo.lock_available(
                    session, tokens=[token, token], bucket_name=BUCKET, now=NOW
                )
                assert len(assets) == 1
                await repo.replace_cart_links(session, cart_id=cart.id, assets=assets)
                await repo.retain_order(session, order_id=order.id, assets=assets)
                await repo.retain_order(session, order_id=order.id, assets=assets)
                assert await session.scalar(
                    select(has_references()).where(MediaObject.id == media.id)
                )
                await session.commit()
                saved_asset_id, saved_media_id = asset.id, media.id
            async with sessions() as session:
                with pytest.raises(IntegrityError):
                    await session.execute(
                        delete(DesignAsset).where(DesignAsset.id == saved_asset_id)
                    )
                await session.rollback()
                assert (
                    await repo.prune_expired(session, now=NOW + timedelta(days=100), limit=1) == []
                )
                assert (
                    await repo.lock_available(
                        session, tokens=[token], bucket_name=BUCKET, now=NOW + timedelta(days=100)
                    )
                )[0].id == saved_asset_id
                await session.commit()
            async with sessions() as session:
                expired = [await seed(session, expiry=NOW - timedelta(hours=1)) for _ in range(3)]
                await session.commit()
                assert len(await repo.prune_expired(session, now=NOW, limit=2)) == 2
                await session.commit()
                assert len(await repo.prune_expired(session, now=NOW, limit=2)) == 1
                await session.commit()
                assert await session.get(MediaObject, saved_media_id) is not None
                with pytest.raises(DesignAssetUnavailableError):
                    await repo.lock_available(
                        session, tokens=[expired[0][0]], bucket_name=BUCKET, now=NOW
                    )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_cart_retention_expires_but_an_active_cart_protects_its_images(cart_database):
    async def scenario():
        engine = create_async_engine(cart_database)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repo = DesignAssetRepository()
        try:
            async with sessions() as session:
                token, asset, media = await seed(session)
                cart = Cart(
                    token_digest_sha256=uuid4().hex * 2, expires_at=NOW + timedelta(days=30)
                )
                session.add(cart)
                await session.flush()
                assets = await repo.lock_available(
                    session, tokens=[token], bucket_name=BUCKET, now=NOW
                )
                await repo.replace_cart_links(session, cart_id=cart.id, assets=assets)
                await session.commit()
                asset_id, media_id = asset.id, media.id
            async with sessions() as session:
                assert await repo.prune_expired(session, now=NOW + timedelta(days=8)) == []
                assert (
                    len(
                        await repo.lock_available(
                            session, tokens=[token], bucket_name=BUCKET, now=NOW + timedelta(days=8)
                        )
                    )
                    == 1
                )
                await session.commit()
            async with sessions() as session:
                assert await repo.prune_expired(session, now=NOW + timedelta(days=31)) == [media_id]
                await session.commit()
                assert await session.get(DesignAsset, asset_id) is None
                assert await session.get(MediaObject, media_id) is not None
                assert not await session.scalar(
                    select(CartDesignAsset.cart_id).where(
                        CartDesignAsset.design_asset_id == asset_id
                    )
                )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_downgrade_refuses_to_drop_live_assets_and_empty_roundtrip_preserves_existing_orders(
    cart_database,
):
    async def retained_order():
        engine = create_async_engine(cart_database)
        try:
            async with async_sessionmaker(engine)() as session:
                token, asset, _ = await seed(session)
                order = Order(
                    items_subtotal=0,
                    delivery_price=0,
                    total_price=0,
                    request_fingerprint_sha256="c" * 64,
                )
                session.add(order)
                await session.flush()
                assets = await DesignAssetRepository().lock_available(
                    session, tokens=[token], bucket_name=BUCKET, now=NOW
                )
                await DesignAssetRepository().retain_order(
                    session, order_id=order.id, assets=assets
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(retained_order())
    with pytest.raises(AssertionError, match="Cannot downgrade while design assets are retained"):
        migrate(cart_database, "downgrade", "20261017_0068")

    async def empty():
        engine = create_async_engine(cart_database)
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(OrderDesignAsset))
                await connection.execute(delete(CartDesignAsset))
                await connection.execute(delete(DesignAsset))
                return (await connection.execute(text("SELECT count(*) FROM orders"))).scalar_one()
        finally:
            await engine.dispose()

    count = asyncio.run(empty())
    migrate(cart_database, "downgrade", "20261017_0068")
    migrate(cart_database, "upgrade", "head")

    async def verify():
        engine = create_async_engine(cart_database)
        try:
            async with engine.connect() as connection:
                assert (
                    await connection.execute(text("SELECT count(*) FROM orders"))
                ).scalar_one() == count
        finally:
            await engine.dispose()

    asyncio.run(verify())


def test_order_attachment_and_cleanup_serialize_and_stale_identity_is_refreshed(cart_database):
    async def scenario():
        engine = create_async_engine(cart_database)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repo = DesignAssetRepository()
        try:
            async with sessions() as session:
                token, asset, media = await seed(session, expiry=NOW + timedelta(minutes=1))
                order = Order(
                    items_subtotal=0,
                    delivery_price=0,
                    total_price=0,
                    request_fingerprint_sha256="d" * 64,
                )
                session.add(order)
                await session.flush()
                await session.commit()
                asset_id, media_id, order_id = asset.id, media.id, order.id
            async with sessions() as writer:
                assets = await repo.lock_available(
                    writer, tokens=[token], bucket_name=BUCKET, now=NOW
                )
                async with sessions() as cleaner:
                    assert await repo.prune_expired(cleaner, now=NOW + timedelta(minutes=2)) == []
                    await cleaner.commit()
                await repo.retain_order(writer, order_id=order_id, assets=assets)
                await writer.commit()
            async with sessions() as stale:
                prefetched = await stale.get(DesignAsset, asset_id)
                assert prefetched.expires_at is None
                prefetched_media = await stale.get(MediaObject, media_id)
                assert prefetched_media.status == "ready"
                await stale.commit()
                async with sessions() as update:
                    current = await update.get(MediaObject, media_id)
                    current.status = "deleted"
                    await update.commit()
                assert prefetched_media.status == "ready"
                with pytest.raises(DesignAssetUnavailableError):
                    await repo.lock_available(stale, tokens=[token], bucket_name=BUCKET, now=NOW)
                assert prefetched_media.status == "deleted"
                await stale.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_batch_lookup_and_cleanup_do_not_query_once_per_image(cart_database):
    async def scenario():
        engine = create_async_engine(cart_database)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repo = DesignAssetRepository()
        try:
            async with sessions() as session:
                rows = [await seed(session) for _ in range(25)]
                await session.commit()
            statements = []

            def capture(conn, cursor, statement, parameters, context, many):
                statements.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", capture)
            async with sessions() as session:
                assert (
                    len(
                        await repo.lock_available(
                            session,
                            tokens=[token for token, _, _ in rows],
                            bucket_name=BUCKET,
                            now=NOW,
                        )
                    )
                    == 25
                )
                assert len(statements) == 2
                await session.commit()
                statements.clear()
                assert len(await repo.prune_expired(session, now=NOW + timedelta(days=8))) == 25
                assert len(statements) == 6
                await session.commit()
            event.remove(engine.sync_engine, "before_cursor_execute", capture)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_shared_media_capabilities_lock_objects_in_one_order_under_concurrent_attachment(
    cart_database,
):
    async def scenario():
        engine = create_async_engine(cart_database)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repo = DesignAssetRepository()
        function = "design_lock_barrier_" + uuid4().hex
        key = int(uuid4().hex[:7], 16)
        tasks = []
        try:
            async with sessions() as session:
                first_token, first, first_media = await seed(session)
                second_token, second, second_media = await seed(session)
                # Each transaction uses distinct capabilities for the same two
                # objects, in opposite capability/object order.
                third_token = uuid4().hex + uuid4().hex[:11]
                fourth_token = uuid4().hex + uuid4().hex[:11]
                third = DesignAsset(
                    media_object_id=second_media.id,
                    access_digest_sha256=digest_design_asset_token(third_token),
                    expires_at=NOW + timedelta(days=7),
                )
                fourth = DesignAsset(
                    media_object_id=first_media.id,
                    access_digest_sha256=digest_design_asset_token(fourth_token),
                    expires_at=NOW + timedelta(days=7),
                )
                session.add_all([third, fourth])
                await session.flush()
                second_ids = [third.id, fourth.id]
                await session.execute(
                    text(f"""
                    CREATE FUNCTION {function}() RETURNS boolean LANGUAGE plpgsql AS $$
                    BEGIN
                        PERFORM pg_advisory_lock({key});
                        PERFORM pg_advisory_unlock({key});
                        RETURN true;
                    END $$
                """)
                )
                await session.commit()

            def barrier(conn, cursor, statement, parameters, context, many):
                if (
                    "JOIN media_objects" in statement
                    and "FOR UPDATE" in statement
                    and "FROM design_assets" in statement
                ):
                    # Evaluated per tuple immediately before its row lock.
                    expression = f", CASE WHEN design_assets.id IN ({second_ids[0]}, {second_ids[1]}) THEN {function}() ELSE true END AS lock_barrier "
                    return statement.replace(
                        "\nFROM design_assets", expression + "\nFROM design_assets", 1
                    ), parameters
                return statement, parameters

            event.listen(engine.sync_engine, "before_cursor_execute", barrier, retval=True)

            async def attach(tokens):
                async with sessions() as session:
                    await session.execute(text("SET LOCAL lock_timeout = '8s'"))
                    assets = await repo.lock_available(
                        session, tokens=tokens, bucket_name=BUCKET, now=NOW
                    )
                    assert len(assets) == 2
                    await session.commit()

            async with engine.connect() as blocker:
                await blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": key})
                try:
                    tasks = [
                        asyncio.create_task(attach([first_token, third_token])),
                        asyncio.create_task(attach([second_token, fourth_token])),
                    ]
                    # Both transactions have reached their second capability.
                    # With interleaved asset/media locks, each holds the object
                    # the other needs and releasing this gate causes a deadlock.
                    async with engine.connect() as observer:
                        for _ in range(200):
                            waiting = await observer.scalar(
                                text(
                                    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = :key AND NOT granted"
                                ),
                                {"key": key},
                            )
                            if waiting == 2:
                                break
                            await asyncio.sleep(0.01)
                        else:
                            raise AssertionError(
                                "Both attachment transactions must reach the lock gate"
                            )
                finally:
                    await blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
            event.remove(engine.sync_engine, "before_cursor_execute", barrier)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            async with engine.begin() as connection:
                await connection.execute(text(f"DROP FUNCTION IF EXISTS {function}()"))
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "changes,expiry",
    [
        ({"status": "pending"}, NOW + timedelta(days=1)),
        ({"status": "deleted"}, NOW + timedelta(days=1)),
        ({"is_public": True}, NOW + timedelta(days=1)),
        ({"provider": "external"}, NOW + timedelta(days=1)),
        ({"bucket_name": "other-private-bucket"}, NOW + timedelta(days=1)),
        ({"content_type": "image/svg+xml"}, NOW + timedelta(days=1)),
        ({}, NOW),
    ],
)
def test_unusable_or_expired_images_cannot_be_attached(cart_database, changes, expiry):
    async def scenario():
        engine = create_async_engine(cart_database)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                token, _, media = await seed(session, expiry=expiry)
                for field, value in changes.items():
                    setattr(media, field, value)
                await session.flush()
                with pytest.raises(DesignAssetUnavailableError):
                    await DesignAssetRepository().lock_available(
                        session, tokens=[token], bucket_name=BUCKET, now=NOW
                    )
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
