from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from time import perf_counter
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event, insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db.base import Base
from app.modules.catalog.admin_repository import product_capacity
from app.modules.catalog.admin_schemas import CatalogAdminQuery
from app.modules.catalog.admin_service import CatalogAdminReadService
from app.modules.catalog.availability import available_stock, load_availability
from app.modules.catalog.editor_options import CatalogEditorOptions, EditorOptionsQuery
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import CatalogAuditEvent, Product, ProductCategory, ProductVariant
from app.modules.catalog.schemas import ProductWriteRequest
from app.modules.catalog.service import (
    CatalogProductVersionConflictError,
    CatalogReferenceNotFoundError,
    CatalogWriteService,
)
from app.modules.crm.reference_models import CrmFabric, CrmGarmentModel
from app.modules.identity.models import User
from app.modules.partners.models import PartnerLanding, PartnerLandingProduct, PartnerProfile
from tests.catalog_admin_fixtures import seed

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


@asynccontextmanager
async def catalog(url):
    schema = "test_catalog_admin_" + uuid4().hex
    engine = create_async_engine(url)
    scoped = engine.execution_options(schema_translate_map={None: schema})
    sessions = async_sessionmaker(scoped, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with scoped.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield SimpleNamespace(session=sessions, engine=scoped), engine, schema
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


def reader():
    return CatalogAdminReadService(CatalogResponseMapper(Settings(_env_file=None, app_env="test")))


def test_native_fabric_capacity_and_all_seek_orders(postgres_url):
    async def scenario():
        async with catalog(postgres_url) as (database, _, _):
            expected = await seed(database)
            async with database.session() as session:
                session.add_all(
                    [
                        Product(title=name, price=10)
                        for name in ["АНЯ", "аня", "ЁЖ", "ёж", "ŽOFIE", "žofie"]
                    ]
                )
                await session.commit()
                rows = list(
                    await session.scalars(select(Product).options(selectinload(Product.variants)))
                )
                await load_availability(session, rows)
                capacity = dict(
                    (await session.execute(select(Product.id, product_capacity()))).all()
                )
                assert capacity == {p.id: available_stock(p) for p in rows}
                assert (
                    capacity[next(key for key, name in expected.items() if name == "Two fabrics")]
                    == 5
                )
                real = [p for p in rows if not p.is_demo]
                for field in ["id", "title", "price", "stock", "variants"]:
                    for direction in ["asc", "desc"]:
                        items, cursor = [], None
                        for _ in range(len(real)):
                            page = await reader().list_page(
                                session,
                                CatalogAdminQuery(
                                    sort=f"{field}:{direction}", limit=2, cursor=cursor
                                ),
                            )
                            items.extend(page.items)
                            cursor = page.next_cursor
                            if cursor is None:
                                break
                        else:
                            raise AssertionError("Pagination did not end")

                        def key(product, field=field):
                            return (
                                {
                                    "id": product.id,
                                    "title": product.title.lower(),
                                    "price": product.price,
                                    "stock": available_stock(product),
                                    "variants": len(product.variants),
                                }[field],
                                product.id,
                            )

                        assert [p.id for p in items] == [
                            p.id for p in sorted(real, key=key, reverse=direction == "desc")
                        ]
                for query, names in [
                    ("аНя", {"АНЯ", "аня"}),
                    ("Ёж", {"ЁЖ", "ёж"}),
                    ("žofie", {"ŽOFIE", "žofie"}),
                    ("_%\\", {"literal_%\\"}),
                ]:
                    result = await reader().list_page(session, CatalogAdminQuery(query=query))
                    assert {p.title for p in result.items} == names

    asyncio.run(scenario())


def test_twenty_thousand_products_return_bounded_pages_and_queries(
    postgres_url, record_testsuite_property
):
    async def scenario():
        async with catalog(postgres_url) as (database, engine, schema):
            expected = await seed(database)
            async with database.session() as session:
                # Half the rows use actual model/fabric capacity, half physical stock.
                linked = await session.scalar(
                    select(Product.garment_model_id).where(Product.title == "Same fabric")
                )
                await session.execute(
                    insert(Product),
                    [
                        {
                            "title": f"Модель {i:05d}",
                            "price": i % 400,
                            "stock_quantity": i % 30,
                            "garment_model_id": linked if i % 2 else None,
                            "preset_source": "user" if i % 3 == 0 else "garment_buro",
                        }
                        for i in range(20000)
                    ],
                )
                await session.commit()
            async with database.engine.begin() as connection:
                await connection.execute(text(f'ANALYZE "{schema}".products'))
            statements = []

            def observe(_conn, _cursor, statement, _params, _context, _many):
                statements.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", observe)
            timings = {}
            try:
                async with database.session() as session:
                    service = reader()
                    counts = await service.counts(session)
                    assert counts.garment_buro + counts.user == 20000 + len(expected)
                    for sort in [
                        "id:desc",
                        "title:asc",
                        "price:asc",
                        "stock:desc",
                        "variants:desc",
                    ]:
                        parameters = CatalogAdminQuery(sort=sort, limit=24)
                        ids = set()
                        durations = []
                        for _ in range(2):
                            statements.clear()
                            started = perf_counter()
                            page = await service.list_page(
                                session, parameters, include_communities=True
                            )
                            durations.append(round((perf_counter() - started) * 1000, 2))
                            assert len(page.items) == 24 and page.next_cursor
                            assert len(statements) <= 6, statements
                            assert ids.isdisjoint(p.id for p in page.items)
                            ids.update(p.id for p in page.items)
                            parameters.cursor = page.next_cursor
                        timings[sort] = durations
                    available = await service.list_page(
                        session, CatalogAdminQuery(stock="available", limit=24)
                    )
                    assert len(available.items) == 24 and all(
                        p.stock_quantity > 0 for p in available.items
                    )
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", observe)
            record_testsuite_property("admin_catalog_20000_page_milliseconds", json.dumps(timings))

    asyncio.run(scenario())


def test_administrative_filters_include_hidden_categories_and_draft_collections(postgres_url):
    async def scenario():
        async with catalog(postgres_url) as (database, _, _):
            await seed(database)
            async with database.session() as session:
                person = User(internal_identity=uuid4().hex)
                category = ProductCategory(
                    name="Архивная категория", slug="archived", is_active=False
                )
                session.add_all([person, category])
                await session.flush()
                partner = PartnerProfile(
                    user_id=person.id, code="owner", display_name="Владелец", commission_bps=1000
                )
                session.add(partner)
                await session.flush()
                landing = PartnerLanding(
                    partner_id=partner.id,
                    slug="draft",
                    title="Коллекция",
                    headline="Коллекция",
                    description="Описание",
                    cta_label="Открыть",
                    cta_href="/",
                    status="draft",
                )
                session.add(landing)
                hidden = await session.scalar(select(Product).where(Product.is_active.is_(False)))
                hidden.category_id = category.id
                hidden.tags = ["Новый тег_%"]
                hidden.preset_source = "user"
                await session.flush()
                session.add(
                    PartnerLandingProduct(landing_id=landing.id, product_id=hidden.id, position=0)
                )
                await session.commit()
                service = reader()
                query = CatalogAdminQuery(
                    category_id=category.id,
                    community_id=landing.id,
                    active=False,
                    source="user",
                    query="НОВЫЙ ТЕГ_%",
                )
                page = await service.list_page(session, query)
                assert [p.id for p in page.items] == [hidden.id]
                assert page.items[0].category_name == "Архивная категория"
                assert (
                    await service.list_page(session, query.model_copy(update={"active": True}))
                ).items == []
                model = await session.scalar(
                    select(Product.garment_model_id).where(Product.title == "Same fabric")
                )
                page = await service.list_page(session, CatalogAdminQuery(garment_model_id=model))
                assert page.items and all(p.garment_model_id == model for p in page.items)
                assert all(p.garment_model_name == "Single" for p in page.items)

    asyncio.run(scenario())


def test_admin_detail_and_update_preserve_sku_identity_and_raw_stock(postgres_url):
    async def scenario():
        async with catalog(postgres_url) as (database, _, _):
            await seed(database)
            settings = Settings(_env_file=None, app_env="test")
            service = CatalogWriteService(settings)
            async with database.session() as session:
                actor = User(internal_identity=uuid4().hex)
                session.add(actor)
                product = await session.scalar(
                    select(Product)
                    .where(Product.title == "Same fabric")
                    .options(selectinload(Product.variants))
                )
                product.variants[0].sku = "stable-sku"
                await session.commit()
                pid, actor_id = product.id, actor.id
                ids = {variant.id for variant in product.variants}
                detail = await reader().detail(session, pid)
                assert detail.stock_quantity == 999 and detail.available_stock_quantity == 3
                assert {variant.id for variant in detail.variants} == ids
                assert all(
                    variant.stock_quantity == 999 and variant.available_stock_quantity == 3
                    for variant in detail.variants
                )
                assert all(variant.fabric_id is not None for variant in detail.variants)
                body = detail.model_dump()
                body["title"] = "Only title changed"
                body["variants"] = list(reversed(body["variants"]))
                updated = await service.update_product(
                    session,
                    product_id=pid,
                    expected_version=body["version"],
                    actor_user_id=actor_id,
                    payload=ProductWriteRequest.model_validate(body),
                )
                await session.commit()
                assert {variant.id for variant in updated.variants} == ids
                refreshed = await reader().detail(session, pid)
                assert refreshed.stock_quantity == 999
                assert any(variant.sku == "stable-sku" for variant in refreshed.variants)
                assert all(variant.stock_quantity == 999 for variant in refreshed.variants)
                body = refreshed.model_dump()
                body["variants"].append(
                    {"size": "new", "fabric_id": refreshed.variants[0].fabric_id}
                )
                await service.update_product(
                    session,
                    product_id=pid,
                    expected_version=body["version"],
                    actor_user_id=actor_id,
                    payload=ProductWriteRequest.model_validate(body),
                )
                await session.commit()
                current = await reader().detail(session, pid)
                assert len(current.variants) == 3 and ids.issubset(
                    {variant.id for variant in current.variants}
                )
                foreign = await session.scalar(
                    select(Product.id).where(Product.title == "Two fabrics")
                )
                other = await reader().detail(session, foreign)
                for variants in [
                    [{**current.variants[0].model_dump(), "id": other.variants[0].id}],
                    [current.variants[0].model_dump(), current.variants[0].model_dump()],
                ]:
                    with pytest.raises(CatalogReferenceNotFoundError):
                        await service.update_product(
                            session,
                            product_id=pid,
                            expected_version=current.version,
                            actor_user_id=actor_id,
                            payload=ProductWriteRequest.model_validate(
                                {**current.model_dump(), "variants": variants}
                            ),
                        )
                    await session.rollback()
                assert len((await reader().detail(session, pid)).variants) == 3
                body = current.model_dump()
                body["variants"] = body["variants"][1:]
                await service.update_product(
                    session,
                    product_id=pid,
                    expected_version=body["version"],
                    actor_user_id=actor_id,
                    payload=ProductWriteRequest.model_validate(body),
                )
                await session.commit()
                remaining = await reader().detail(session, pid)
                assert {v.id for v in remaining.variants} == {v.id for v in current.variants[1:]}
                assert await reader().detail(session, 2_147_483_647) is None

    asyncio.run(scenario())


def test_editor_choices_search_and_continue_past_first_hundred(postgres_url):
    async def scenario():
        async with catalog(postgres_url) as (database, _, _):
            await seed(database)
            async with database.session() as session:
                await session.execute(
                    insert(CrmGarmentModel),
                    [{"code": f"CHOICE_{i}", "name": f"МОДЕЛЬ {i:03d}"} for i in range(130)],
                )
                await session.execute(
                    insert(CrmFabric),
                    [
                        {
                            "code": f"CHOICE_F_{i}",
                            "name": f"ТКАНЬ {i:03d}",
                            "color_name": "Белый",
                            "width_cm": 150,
                        }
                        for i in range(130)
                    ],
                )
                await session.commit()
                for method, expected in [
                    (CatalogEditorOptions.models, 132),
                    (CatalogEditorOptions.fabrics, 133),
                ]:
                    cursor, ids = None, []
                    for _ in range(10):
                        page = await method(session, EditorOptionsQuery(limit=24, cursor=cursor))
                        assert len(page.items) <= 24
                        ids.extend(row.id for row in page.items)
                        cursor = page.next_cursor
                        if cursor is None:
                            break
                    else:
                        raise AssertionError("Lookup did not end")
                    assert len(ids) == expected and len(set(ids)) == expected
                page = await CatalogEditorOptions.models(
                    session, EditorOptionsQuery(query="модель 129")
                )
                assert len(page.items) == 1
                selected = await CatalogEditorOptions.model(session, page.items[0].id)
                assert selected.name == "МОДЕЛЬ 129"
                page = await CatalogEditorOptions.fabrics(
                    session, EditorOptionsQuery(query="ткань 129")
                )
                assert len(page.items) == 1
                fabrics = await CatalogEditorOptions.selected_fabrics(session, [page.items[0].id])
                assert fabrics[0].name == "ТКАНЬ 129"
                model = await session.scalar(
                    select(Product.garment_model_id).where(Product.title == "Same fabric")
                )
                allowed = await CatalogEditorOptions.fabrics(
                    session, EditorOptionsQuery(model_id=model)
                )
                assert len(allowed.items) == 1 and allowed.items[0].name == "Fabric0"
                assert not (
                    await CatalogEditorOptions.models(session, EditorOptionsQuery(query="_%"))
                ).items

    asyncio.run(scenario())


def test_product_version_rejects_a_waiting_writer_with_a_stale_identity_map(postgres_url):
    async def scenario():
        async with catalog(postgres_url) as (database, _, _):
            service = CatalogWriteService(Settings(_env_file=None, app_env="test"))
            async with database.session() as session:
                actor = User(internal_identity=uuid4().hex)
                product = Product(
                    title="Original",
                    price=80,
                    stock_quantity=7,
                    variants=[ProductVariant(size="M", stock_quantity=7, sku="stable")],
                )
                session.add_all([actor, product])
                await session.commit()
                pid, actor_id = product.id, actor.id
            async with database.session() as winner, database.session() as loser:
                # Preload both sessions; the second lock must refresh an existing ORM object.
                first = await reader().detail(winner, pid)
                stale = await reader().detail(loser, pid)
                assert first.version == stale.version == 1
                # Separate GET and PUT transactions, as the HTTP helper does. Keep
                # the identity maps (expire_on_commit=False), release FOR SHARE.
                await winner.commit()
                await loser.commit()
                loser_pid = await loser.scalar(text("SELECT pg_backend_pid()"))
                updated = await asyncio.wait_for(
                    service.update_product(
                        winner,
                        product_id=pid,
                        expected_version=first.version,
                        payload=ProductWriteRequest.model_validate(
                            {**first.model_dump(), "title": "Winner"}
                        ),
                        actor_user_id=actor_id,
                    ),
                    timeout=5,
                )
                assert updated.version == 2
                pending = asyncio.create_task(
                    service.update_product(
                        loser,
                        product_id=pid,
                        expected_version=stale.version,
                        payload=ProductWriteRequest.model_validate(
                            {**stale.model_dump(), "title": "Lost", "stock_quantity": 999}
                        ),
                        actor_user_id=actor_id,
                    )
                )
                try:
                    # Verify the losing transaction really waits on a PostgreSQL lock.
                    async with database.engine.connect() as observer:
                        observer = await observer.execution_options(isolation_level="AUTOCOMMIT")
                        async with asyncio.timeout(5):
                            while (
                                await observer.scalar(
                                    text(
                                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"
                                    ),
                                    {"pid": loser_pid},
                                )
                                != "Lock"
                            ):
                                await asyncio.sleep(0.01)
                    await winner.commit()
                    with pytest.raises(CatalogProductVersionConflictError):
                        await asyncio.wait_for(pending, timeout=5)
                    await loser.rollback()
                finally:
                    if not pending.done():
                        pending.cancel()
                        await asyncio.gather(pending, return_exceptions=True)
            async with database.session() as session:
                final = await reader().detail(session, pid)
                assert (final.title, final.stock_quantity, final.version) == ("Winner", 7, 2)
                assert final.variants[0].sku == "stable"
                assert final.variants[0].id == stale.variants[0].id
                events = list(await session.scalars(select(CatalogAuditEvent)))
                assert len(events) == 1 and events[0].action == "product.updated"

    asyncio.run(scenario())
