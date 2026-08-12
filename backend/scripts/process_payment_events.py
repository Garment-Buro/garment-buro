from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.payments.provider import (
    AiohttpYooKassaTransport,
    YooKassaProvider,
    YooKassaProviderClient,
)
from app.modules.payments.worker import PaymentEventProcessor

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify and process durable payment events")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Drain up to --max-items and exit instead of polling forever",
    )
    parser.add_argument("--max-items", type=int, default=100)
    parser.add_argument("--poll-seconds", type=float)
    return parser.parse_args()


async def process_batch(
    database: DatabaseManager,
    provider: YooKassaProvider,
    *,
    max_items: int,
    worker_id: str,
) -> int:
    processor = PaymentEventProcessor(database.settings, provider)
    processed = 0
    for _ in range(max_items):
        async with database.session() as session:
            result = await processor.process_once(
                session,
                now=_utc_now(),
                worker_id=worker_id,
            )
        if result is None:
            break
        processed += 1
        logger.info(
            "Payment event %s finished attempt %s with status %s error %s",
            result.event_id,
            result.attempt_number,
            result.status,
            result.error_code or "none",
        )
    return processed


async def run(args: argparse.Namespace) -> None:
    if not 1 <= args.max_items <= 1_000:
        raise ValueError("--max-items must be between 1 and 1000")
    settings = get_settings()
    if not settings.database_enabled:
        raise RuntimeError("DATABASE_ENABLED is required for the payment worker")
    poll_seconds = (
        args.poll_seconds
        if args.poll_seconds is not None
        else float(settings.payment_event_poll_seconds)
    )
    if poll_seconds <= 0:
        raise ValueError("--poll-seconds must be positive")

    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    database = DatabaseManager(settings)
    transport = AiohttpYooKassaTransport(settings)
    provider = YooKassaProviderClient(transport)
    await database.startup()
    try:
        await transport.startup()
        while True:
            processed = await process_batch(
                database,
                provider,
                max_items=args.max_items,
                worker_id=worker_id,
            )
            if args.once:
                return
            if processed == 0:
                await asyncio.sleep(poll_seconds)
    finally:
        await transport.shutdown()
        await database.shutdown()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
