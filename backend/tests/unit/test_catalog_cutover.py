from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.cutover import verify_catalog_cutover
from app.modules.catalog.models import CatalogMigrationRun, Product


def test_catalog_cutover_allows_reviewed_writes_after_strict_import(tmp_path: Path) -> None:
    async def scenario() -> None:
        fingerprint = "a" * 64
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'cutover.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                session.add(
                    CatalogMigrationRun(
                        fingerprint_sha256=fingerprint,
                        products_count=0,
                        variants_count=0,
                        media_count=0,
                        media_references_count=0,
                    )
                )
                await session.commit()

            await verify_catalog_cutover(database, fingerprint)

            async with database.session() as session:
                session.add(Product(title="Created after cutover", price=100))
                await session.commit()

            with pytest.raises(ConfigurationError, match="target counts"):
                await verify_catalog_cutover(database, fingerprint)
            await verify_catalog_cutover(database, fingerprint, allow_mutations=True)
        finally:
            await database.shutdown()

    asyncio.run(scenario())
