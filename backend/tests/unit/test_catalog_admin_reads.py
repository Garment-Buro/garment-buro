from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.admin_repository import product_capacity
from app.modules.catalog.admin_schemas import CatalogAdminQuery
from app.modules.catalog.admin_service import CatalogAdminReadService, InvalidCatalogAdminCursor
from app.modules.catalog.availability import available_stock, load_availability
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import Product
from tests.catalog_admin_fixtures import seed


def test_admin_stock_query_matches_checkout_capacity_without_double_counting(tmp_path):
    async def scenario():
        settings = Settings(
            _env_file=None,
            app_env="test",
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'stock.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await seed(database)
            async with database.session() as session:
                values = dict((await session.execute(select(Product.id, product_capacity()))).all())
                products = list(
                    await session.scalars(select(Product).options(selectinload(Product.variants)))
                )
                await load_availability(session, products)
                assert values == {p.id: available_stock(p) for p in products}
                by_title = {p.title: values[p.id] for p in products}
                assert by_title["Same fabric"] == by_title["Single no variants"] == 3
                assert by_title["Inferred single"] == 3
                assert by_title["Two fabrics"] == 5
                for title in [
                    "Ambiguous",
                    "Multi no variants",
                    "Inactive model",
                    "Unrelated fabric",
                ]:
                    assert by_title[title] == 0
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_admin_pagination_filters_and_cursor_boundaries(tmp_path):
    async def scenario():
        settings = Settings(
            _env_file=None,
            app_env="test",
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'pages.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            expected = await seed(database)
            service = CatalogAdminReadService(CatalogResponseMapper(settings))
            async with database.session() as session:
                for field in ["id", "title", "price", "stock", "variants"]:
                    for direction in ["asc", "desc"]:
                        cursor, items = None, []
                        for _ in range(10):
                            page = await service.list_page(
                                session,
                                CatalogAdminQuery(
                                    sort=f"{field}:{direction}", limit=2, cursor=cursor
                                ),
                            )
                            assert len(page.items) <= 2
                            items.extend(page.items)
                            cursor = page.next_cursor
                            if cursor is None:
                                break
                        else:
                            raise AssertionError("Pagination did not end")
                        assert len(items) == len(expected)
                        assert {p.id for p in items} == set(expected)

                        def key(product, field=field):
                            value = {
                                "id": product.id,
                                "title": product.title.lower(),
                                "price": product.price,
                                "stock": product.stock_quantity,
                                "variants": product.variant_count,
                            }[field]
                            return value, product.id

                        assert items == sorted(items, key=key, reverse=direction == "desc")
                page = await service.list_page(session, CatalogAdminQuery(limit=1))
                assert page.next_cursor
                for query in [
                    CatalogAdminQuery(cursor="invalid!"),
                    CatalogAdminQuery(cursor=page.next_cursor, source="user"),
                    CatalogAdminQuery(cursor=page.next_cursor, sort="stock:desc"),
                ]:
                    with pytest.raises(InvalidCatalogAdminCursor):
                        await service.list_page(session, query)
                literal = await service.list_page(session, CatalogAdminQuery(query="_%\\"))
                assert [p.title for p in literal.items] == ["literal_%\\"]
                stock = await service.list_page(session, CatalogAdminQuery(stock="available"))
                assert stock.items and all(p.stock_quantity > 0 for p in stock.items)
                empty = await service.list_page(session, CatalogAdminQuery(stock="empty"))
                assert empty.items and all(p.stock_quantity == 0 for p in empty.items)
                users = await service.list_page(session, CatalogAdminQuery(source="user"))
                assert len(users.items) == 1
                counts = await service.counts(session)
                assert counts.user == 1 and counts.garment_buro == len(expected) - 1
        finally:
            await database.shutdown()

    asyncio.run(scenario())
