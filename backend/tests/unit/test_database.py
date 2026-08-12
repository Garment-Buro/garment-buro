from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.session import DatabaseManager, normalize_async_database_url


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "postgresql://user:password@db/example",
            "postgresql+asyncpg://user:password@db/example",
        ),
        (
            "postgres://user:password@db/example",
            "postgresql+asyncpg://user:password@db/example",
        ),
        ("sqlite:///example.db", "sqlite+aiosqlite:///example.db"),
        (
            "postgresql+asyncpg://user:password@db/example",
            "postgresql+asyncpg://user:password@db/example",
        ),
    ],
)
def test_async_database_urls_are_normalized(source: str, expected: str) -> None:
    assert normalize_async_database_url(source) == expected


def test_database_manager_lifecycle_and_transaction_rollback() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)

        await database.startup()
        assert database.backend_name == "sqlite"
        assert await database.ping()

        async with database.engine.begin() as connection:
            await connection.execute(text("CREATE TABLE probe (value INTEGER NOT NULL)"))

        with pytest.raises(RuntimeError, match="rollback probe"):
            async with database.session() as session:
                await session.execute(text("INSERT INTO probe (value) VALUES (42)"))
                raise RuntimeError("rollback probe")

        async with database.engine.connect() as connection:
            count = await connection.scalar(text("SELECT COUNT(*) FROM probe"))
        assert count == 0

        await database.shutdown()
        with pytest.raises(ConfigurationError, match="has not been started"):
            _ = database.engine

    asyncio.run(scenario())


def test_disabled_database_manager_is_explicitly_legacy() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=False,
        database_url=None,
    )
    database = DatabaseManager(settings)

    assert database.backend_name == "legacy"
    assert not asyncio.run(database.ping())
