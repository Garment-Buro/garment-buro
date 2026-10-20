"""Wait for a stopped migration's PostgreSQL session, without changing data."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence

from sqlalchemy import make_url, pool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.migration_lock import acquire_migration_lock


async def run(environment: Mapping[str, str]) -> None:
    url = make_url(environment.get("DATABASE_URL", ""))
    if (
        url.drivername not in {"postgresql", "postgresql+asyncpg", "postgres"}
        or not url.host
        or not url.database
        or not url.username
    ):
        raise ValueError("PostgreSQL DATABASE_URL is required")
    engine = create_async_engine(
        url.set(drivername="postgresql+asyncpg"),
        poolclass=pool.NullPool,
        connect_args={
            "timeout": 5,
            "command_timeout": 45,
            "server_settings": {
                "application_name": "garment-buro-migration-wait",
                "lock_timeout": "30000",
                "statement_timeout": "45000",
            },
        },
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(acquire_migration_lock)
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        asyncio.run(run(os.environ))
    except (SQLAlchemyError, OSError, TimeoutError, TypeError, ValueError) as error:
        print(
            json.dumps(
                {"event": "database.migration_wait_failed", "error_type": type(error).__name__}
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"event": "database.migration_idle"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
