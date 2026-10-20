from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.test_cart_revisions_postgres import cart_database as cart_database
from tests.postgres_schema import migrate, seed_historical_product

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_product_version_migration_preserves_existing_rows_and_checks_positive_versions(
    cart_database,
):
    migrate(cart_database, "downgrade", "20261017_0069")

    async def action(name):
        engine = create_async_engine(cart_database)
        try:
            async with engine.begin() as connection:
                if name == "seed":
                    return await seed_historical_product(
                        connection, title="Historical product", stock_quantity=7
                    )
                row = (
                    await connection.execute(
                        text("SELECT title,stock_quantity,version FROM products WHERE id=:id"),
                        {"id": product_id},
                    )
                ).one()
                assert row == ("Historical product", 7, 1)
                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(
                            text("UPDATE products SET version=0 WHERE id=:id"), {"id": product_id}
                        )
        finally:
            await engine.dispose()

    product_id = asyncio.run(action("seed"))
    migrate(cart_database, "upgrade", "head")
    asyncio.run(action("verify"))
    migrate(cart_database, "downgrade", "20261017_0069")
    migrate(cart_database, "upgrade", "head")
    asyncio.run(action("verify"))
