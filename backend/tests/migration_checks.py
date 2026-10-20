from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.core.config import Settings
from app.db.session import DatabaseManager


def check_migration(
    settings: Settings,
    verifier: Callable[[DatabaseManager, str], Awaitable[None]],
    fingerprint: str,
) -> None:
    """Exercise the offline data-import check independently of API startup."""

    async def run():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            await verifier(database, fingerprint)
        finally:
            await database.shutdown()

    asyncio.run(run())
