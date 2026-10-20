from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event, make_url, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import AppEnvironment, Settings
from app.modules.carts.models import Cart, CartItem
from app.modules.carts.schemas import CartUpdateRequest
from app.modules.carts.service import CartMaintenanceService, CartRevisionConflictError, CartService
from tests.contract.test_cart_revisions import write
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


@pytest.fixture(scope="module")
def cart_database():
    source = make_url(os.environ["SCHEMA_TEST_POSTGRES_URL"])
    assert (source.database or "").startswith("test_")
    name = "test_cart_" + uuid4().hex
    url = source.set(database=name).render_as_string(hide_password=False)

    async def manage(action):
        engine = create_async_engine(source, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                await connection.execute(
                    text(
                        f'{action} DATABASE "{name}"'
                        + (" WITH (FORCE)" if action == "DROP" else "")
                    )
                )
        finally:
            await engine.dispose()

    asyncio.run(manage("CREATE"))
    try:
        migrate(url, "upgrade", "head")
        yield url
    finally:
        asyncio.run(manage("DROP"))


def service(url):
    return CartService(
        Settings(
            _env_file=None, app_env=AppEnvironment.TEST, database_enabled=True, database_url=url
        )
    )


def test_simultaneous_create_update_and_preloaded_identity_cannot_overwrite(cart_database):
    async def scenario():
        engine = create_async_engine(cart_database)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        carts = service(cart_database)
        try:
            token = uuid4().hex

            async def race(revision):
                start = asyncio.Event()

                async def writer(quantity):
                    async with sessions() as session:
                        await start.wait()
                        try:
                            saved = await carts.upsert_snapshot(
                                session,
                                cart_id=token,
                                payload=CartUpdateRequest.model_validate(
                                    write(revision, quantity=quantity)
                                ),
                            )
                            await session.commit()
                            return saved
                        except CartRevisionConflictError:
                            await session.rollback()
                            return None

                jobs = [asyncio.create_task(writer(i)) for i in [2, 3]]
                start.set()
                results = await asyncio.gather(*jobs)
                assert sum(result is not None for result in results) == 1
                winner = next(result for result in results if result is not None)
                async with sessions() as session:
                    current = await carts.get_snapshot(session, cart_id=token)
                    assert current == winner
                return winner

            created = await race(None)
            updated = await race(created.revision)
            async with sessions() as stale:
                cached = await carts.get_snapshot(stale, cart_id=token)
                async with sessions() as other:
                    newer = await carts.upsert_snapshot(
                        other,
                        cart_id=token,
                        payload=CartUpdateRequest.model_validate(
                            write(updated.revision, quantity=9)
                        ),
                    )
                    await other.commit()
                with pytest.raises(CartRevisionConflictError):
                    await carts.upsert_snapshot(
                        stale,
                        cart_id=token,
                        payload=CartUpdateRequest.model_validate(write(cached.revision)),
                    )
                await stale.rollback()
                # Revision and items are read by one SQL statement, one MVCC snapshot.
                statements = []
                event.listen(
                    engine.sync_engine,
                    "before_cursor_execute",
                    lambda *args: statements.append(args[2]),
                )
                current = await carts.get_snapshot(stale, cart_id=token)
                assert current == newer
                assert len(statements) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_exact_replay_retains_ttl_and_expired_or_purged_revisions_do_not_match(cart_database):
    async def scenario():
        engine = create_async_engine(cart_database)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        carts, token = service(cart_database), uuid4().hex
        now = datetime.now(timezone.utc)
        try:
            request = CartUpdateRequest.model_validate(write())
            async with sessions() as session:
                first = await carts.upsert_snapshot(
                    session, cart_id=token, payload=request, now=now
                )
                await session.commit()
                expiry = (
                    await session.scalar(select(Cart).where(Cart.revision == first.revision))
                ).expires_at
            async with sessions() as session:
                replay = await carts.upsert_snapshot(
                    session, cart_id=token, payload=request, now=now + timedelta(seconds=10)
                )
                assert replay == first
                assert (
                    await session.scalar(select(Cart).where(Cart.revision == first.revision))
                ).expires_at == expiry
                await session.commit()
            after = expiry + timedelta(seconds=1)
            async with sessions() as session:
                assert (
                    await carts.get_snapshot(session, cart_id=token, now=after)
                ).revision is None
                with pytest.raises(CartRevisionConflictError):
                    await carts.upsert_snapshot(session, cart_id=token, payload=request, now=after)
                await session.rollback()
                with pytest.raises(CartRevisionConflictError):
                    await carts.upsert_snapshot(
                        session,
                        cart_id=token,
                        payload=CartUpdateRequest.model_validate(write(first.revision)),
                        now=after,
                    )
                await session.rollback()
                await CartMaintenanceService().purge_expired(session, now=after)
                await session.commit()
            async with sessions() as session:
                with pytest.raises(CartRevisionConflictError):
                    await carts.upsert_snapshot(
                        session,
                        cart_id=token,
                        payload=CartUpdateRequest.model_validate(write(first.revision)),
                        now=after,
                    )
                await session.rollback()
                created = await carts.upsert_snapshot(
                    session,
                    cart_id=token,
                    payload=CartUpdateRequest.model_validate(write()),
                    now=after,
                )
                await session.commit()
                assert created.revision != first.revision
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_migration_preserves_existing_cart_items_and_roundtrips(cart_database):
    migrate(cart_database, "downgrade", "20261017_0067")

    async def data(action):
        engine = create_async_engine(cart_database)
        try:
            async with engine.begin() as connection:
                if action == "seed":
                    for _i in [1, 2]:
                        cart_id = await connection.scalar(
                            text(
                                "INSERT INTO carts(token_digest_sha256,client_updated_at_ms,expires_at,version) VALUES (:digest,123456789,now()+interval '30 days',7) RETURNING id"
                            ),
                            {"digest": uuid4().hex * 2},
                        )
                        await connection.execute(
                            text(
                                "INSERT INTO cart_items(cart_id,client_item_id,product_id_snapshot,title_snapshot,unit_price,image_url_snapshot,size_snapshot,color_snapshot,quantity,sort_order,customization_snapshot) VALUES (:id,'item',7,'Сохранить',1080,'/fixture','M','black',2,0,CAST(:customization AS JSON))"
                            ),
                            {"id": cart_id, "customization": '{"fit":{"lengthCm":70}}'},
                        )
                carts = (
                    await connection.execute(
                        text("SELECT id,token_digest_sha256,expires_at FROM carts ORDER BY id")
                    )
                ).all()
                items = (
                    await connection.execute(select(CartItem.__table__).order_by(CartItem.id))
                ).all()
                timestamp = "updated_at_ms" if action == "head" else "client_updated_at_ms"
                times = (
                    (await connection.execute(text(f"SELECT {timestamp} FROM carts ORDER BY id")))
                    .scalars()
                    .all()
                )
                revisions = (
                    (await connection.execute(text("SELECT revision FROM carts ORDER BY id")))
                    .scalars()
                    .all()
                    if action == "head"
                    else []
                )
                return carts, items, times, revisions
        finally:
            await engine.dispose()

    before = asyncio.run(data("seed"))
    try:
        migrate(cart_database, "upgrade", "head")
        after = asyncio.run(data("head"))
        assert after[:3] == before[:3]
        assert len(set(after[3])) == len(after[3])
        assert all(len(revision) == 32 for revision in after[3])
        migrate(cart_database, "downgrade", "20261017_0067")
        assert asyncio.run(data("old")) == before
    finally:
        migrate(cart_database, "upgrade", "head")
