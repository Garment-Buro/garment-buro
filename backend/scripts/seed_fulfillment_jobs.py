from __future__ import annotations

import argparse
import asyncio
import json

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.fulfillment.service import FulfillmentOutboxService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Schedule missing fulfillment jobs for verified paid orders"
    )
    parser.add_argument("--limit", type=int, default=100)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, int]:
    if not 1 <= args.limit <= 1_000:
        raise ValueError("--limit must be between 1 and 1000")
    settings = get_settings()
    if not settings.fulfillment_outbox_enabled:
        raise RuntimeError("FULFILLMENT_OUTBOX_ENABLED is required")
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            scheduled = await FulfillmentOutboxService(settings).seed_paid_orders(
                session,
                limit=args.limit,
            )
            await session.commit()
    finally:
        await database.shutdown()
    return {"scheduled_jobs": scheduled}


def main() -> int:
    try:
        result = asyncio.run(run(parse_args()))
    except (RuntimeError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
