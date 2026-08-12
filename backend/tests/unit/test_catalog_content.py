from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.content import (
    CatalogContentError,
    CatalogContentMigrationService,
    CatalogContentService,
    LandingSettings,
    LegacyCatalogContentPlanner,
    verify_catalog_content_cutover,
)
from app.modules.identity.models import User


def test_catalog_content_plan_is_deterministic_and_uses_reviewable_defaults(
    tmp_path: Path,
) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "settings.json").write_text(
        json.dumps(
            {
                "logo_video_url": "/logo.mp4",
                "hero_products": [4, 3],
                "showroom1_products": [2],
                "showroom2_products": [1],
                "links": {},
            }
        ),
        encoding="utf-8",
    )

    first = LegacyCatalogContentPlanner().build(uploads)
    second = LegacyCatalogContentPlanner().build(uploads)

    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    assert first.settings_source == "file"
    assert first.options_source == "default"
    assert first.report()["counts"] == {"links": 0, "colors": 2, "sizes": 6}

    (uploads / "variant_options.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(CatalogContentError, match="variant_options.json"):
        LegacyCatalogContentPlanner().build(uploads)


def test_catalog_content_migration_is_idempotent_and_cutover_is_guarded(tmp_path: Path) -> None:
    async def scenario() -> None:
        plan = LegacyCatalogContentPlanner().build(tmp_path / "uploads")
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'content.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                session.add(
                    User(
                        id=1,
                        email="manager@example.test",
                        email_normalized="manager@example.test",
                    )
                )
                first = await CatalogContentMigrationService().apply(session, plan)
                await session.commit()
                assert first.documents == 2
            async with database.session() as session:
                repeated = await CatalogContentMigrationService().apply(session, plan)
                await session.commit()
                assert repeated.documents == 2

            async with database.session() as session:
                await CatalogContentService().update_settings(
                    session,
                    payload=LandingSettings(logo_video_url="/updated.mp4"),
                    actor_user_id=1,
                )
                await session.commit()
            async with database.session() as session:
                repeated_after_update = await CatalogContentMigrationService().apply(session, plan)
                await session.commit()
                assert repeated_after_update.documents == 2

            await verify_catalog_content_cutover(database, plan.fingerprint)
            with pytest.raises(ConfigurationError, match="not present"):
                await verify_catalog_content_cutover(database, "f" * 64)
        finally:
            await database.shutdown()

    asyncio.run(scenario())
