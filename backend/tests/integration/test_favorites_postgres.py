from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db.session import DatabaseManager
from app.factory import create_app
from app.modules.catalog.models import Product, ProductCategory
from app.modules.favorites.models import UserFavorite
from app.modules.identity.models import User
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL test database"
)
FAVORITES = "/api/profile/favorites"


def test_concurrent_favorites_and_foreign_key_cleanup_on_postgres(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    settings = favorite_settings(postgres_url)
    products, (owner, other), users = asyncio.run(seed_favorites(settings, create_schema=False))

    async def database_operation(operation):
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                result = await operation(session)
                await session.commit()
                return result
        finally:
            await database.shutdown()

    async def favorite_count(session):
        return await session.scalar(
            select(func.count())
            .select_from(UserFavorite)
            .where(UserFavorite.product_id == products[0])
        )

    async def delete_product(session):
        await session.execute(delete(Product).where(Product.id == products[0]))

    async def delete_owner(session):
        await session.execute(delete(User).where(User.id == users[0]))

    async def cleanup(session):
        categories = list(
            await session.scalars(
                select(Product.category_id).where(
                    Product.id.in_(products), Product.category_id.is_not(None)
                )
            )
        )
        await session.execute(delete(User).where(User.id.in_(users)))
        await session.execute(delete(Product).where(Product.id.in_(products)))
        await session.execute(delete(ProductCategory).where(ProductCategory.id.in_(categories)))

    try:
        with TestClient(create_app(settings=settings)) as client:

            def save(_):
                return client.put(f"{FAVORITES}/{products[0]}", headers=owner).status_code

            with ThreadPoolExecutor(max_workers=4) as executor:
                assert list(executor.map(save, range(12))) == [204] * 12
            assert asyncio.run(database_operation(favorite_count)) == 1
        # A new application, engine and client use the same persisted account data.
        with TestClient(create_app(settings=settings)) as client:
            assert len(client.get(FAVORITES, headers=owner).json()["items"]) == 1
            assert client.put(f"{FAVORITES}/{products[0]}", headers=other).status_code == 204
            asyncio.run(database_operation(delete_product))
            assert asyncio.run(database_operation(favorite_count)) == 0
            for account in (owner, other):
                assert client.get(FAVORITES, headers=account).json()["items"] == []
            assert client.put(f"{FAVORITES}/{products[1]}", headers=owner).status_code == 204
            assert client.put(f"{FAVORITES}/{products[2]}", headers=other).status_code == 204
            asyncio.run(database_operation(delete_owner))
            assert client.get(FAVORITES, headers=owner).status_code == 401
            assert [
                item["product_id"] for item in client.get(FAVORITES, headers=other).json()["items"]
            ] == [products[2]]
    finally:
        asyncio.run(database_operation(cleanup))
