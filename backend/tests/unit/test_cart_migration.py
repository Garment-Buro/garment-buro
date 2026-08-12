from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.carts.cutover import verify_cart_cutover
from app.modules.carts.migration import (
    CartMigrationError,
    CartMigrationService,
    LegacyCartPlanner,
    LegacyCartSourceEntry,
)
from app.modules.carts.models import CartMigrationRun
from app.modules.carts.service import CartService
from scripts.migrate_legacy_carts import read_legacy_entries


def _legacy_payload(title: str, updated_at_ms: int) -> str:
    return json.dumps(
        {
            "updated_at_ms": updated_at_ms,
            "items": [
                {
                    "id": f"1_M_{title}",
                    "product_id": 1,
                    "title": title,
                    "price": 1000,
                    "image": "",
                    "size": "M",
                    "color": title,
                    "quantity": 1,
                }
            ],
        }
    )


def test_cart_migration_plan_is_deterministic_and_pii_minimized() -> None:
    first = LegacyCartPlanner().build(
        {
            "cart:session:guest-second": _legacy_payload("Second", 2),
            "cart:session:guest-first": _legacy_payload("First", 1),
        }
    )
    second = LegacyCartPlanner().build(
        {
            "cart:session:guest-first": _legacy_payload("First", 1),
            "cart:session:guest-second": _legacy_payload("Second", 2),
        }
    )

    assert first.fingerprint == second.fingerprint
    assert first.report() == {
        "valid": True,
        "fingerprint_sha256": first.fingerprint,
        "carts_count": 2,
        "items_count": 2,
    }
    assert "guest-first" not in json.dumps(first.report())
    with pytest.raises(CartMigrationError, match="invalid"):
        LegacyCartPlanner().build({"cart:session:bad": "{broken"})
    with pytest.raises(CartMigrationError, match="positive update timestamp"):
        LegacyCartPlanner().build(
            {
                "cart:session:guest-missing-time": json.dumps(
                    {"items": []},
                )
            }
        )
    with pytest.raises(CartMigrationError, match="active expiry"):
        LegacyCartPlanner().build(
            {
                "cart:session:guest-expired": LegacyCartSourceEntry(
                    _legacy_payload("Expired", 1),
                    remaining_ttl_seconds=0,
                )
            }
        )


def test_cart_migration_source_errors_do_not_echo_the_redis_url() -> None:
    redis_url = "not-a-redis-url-with-secret"

    with pytest.raises(CartMigrationError) as captured:
        read_legacy_entries(redis_url)

    assert str(captured.value) == "Legacy Redis cart source is unavailable"
    assert redis_url not in str(captured.value)


def test_cart_migration_apply_and_cutover_are_idempotent(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}",
        )
        imported_updated_at_ms = 1_900_000_000_000
        plan = LegacyCartPlanner().build(
            {
                "cart:session:guest-contract": LegacyCartSourceEntry(
                    _legacy_payload("Imported", imported_updated_at_ms),
                    remaining_ttl_seconds=120,
                )
            }
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            migration = CartMigrationService(settings)
            async with database.session() as session:
                applied = await migration.apply(
                    session,
                    plan,
                    now=datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc),
                )
                await session.commit()
                assert applied.carts == 1 and applied.items == 1
            async with database.session() as session:
                repeated = await migration.apply(session, plan)
                await session.commit()
                assert repeated.fingerprint_sha256 == plan.fingerprint

            await verify_cart_cutover(database, plan.fingerprint)
            with pytest.raises(ConfigurationError, match="not present"):
                await verify_cart_cutover(database, "f" * 64)
            async with database.session() as session:
                snapshot = await CartService(settings).get_snapshot(
                    session,
                    cart_id="guest-contract",
                    now=datetime(2026, 8, 11, 10, 1, tzinfo=timezone.utc),
                )
                assert snapshot.items[0].title == "Imported"
                assert snapshot.updated_at_ms == imported_updated_at_ms
            async with database.session() as session:
                expired = await CartService(settings).get_snapshot(
                    session,
                    cart_id="guest-contract",
                    now=datetime(2026, 8, 11, 10, 2, tzinfo=timezone.utc),
                )
                assert expired.items == []
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cart_migration_refuses_a_nonempty_unreviewed_target(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'nonempty.db'}",
        )
        plan = LegacyCartPlanner().build({})
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                session.add(
                    CartMigrationRun(
                        fingerprint_sha256="f" * 64,
                        carts_count=0,
                        items_count=0,
                    )
                )
                await session.commit()
            async with database.session() as session:
                with pytest.raises(CartMigrationError, match="must be empty"):
                    await CartMigrationService(settings).apply(session, plan)
        finally:
            await database.shutdown()

    asyncio.run(scenario())
