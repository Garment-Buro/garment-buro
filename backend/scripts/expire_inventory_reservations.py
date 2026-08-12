from __future__ import annotations

import argparse
import asyncio
import json

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.orders.service import OrderLifecycleService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expire pending inventory reservations")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, int]:
    settings = get_settings()
    if not settings.database_enabled:
        raise RuntimeError("DATABASE_ENABLED is required")
    database = DatabaseManager(settings)
    await database.startup()
    expired = 0
    batches = 0
    try:
        while True:
            async with database.session() as session:
                count = await OrderLifecycleService(settings).expire_pending(
                    session,
                    batch_size=args.batch_size,
                )
                await session.commit()
            expired += count
            batches += 1 if count else 0
            if args.once or count < args.batch_size:
                break
    finally:
        await database.shutdown()
    return {"expired_orders": expired, "batches": batches}


def main() -> int:
    args = parse_args()
    try:
        result = asyncio.run(run(args))
    except (RuntimeError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
