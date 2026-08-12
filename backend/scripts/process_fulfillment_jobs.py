from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.fulfillment.factory import build_fulfillment_processor

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process supported post-payment fulfillment handoffs"
    )
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
    *,
    max_items: int,
    worker_id: str,
) -> int:
    processor = build_fulfillment_processor(database.settings)
    processed = 0
    for _ in range(max_items):
        async with database.session() as session:
            result = await processor.process_once(
                session,
                worker_id=worker_id,
                now=_utc_now(),
            )
        if result is None:
            break
        processed += 1
        logger.info(
            "Fulfillment job %s kind %s finished attempt %s with status %s error %s",
            result.job_id,
            result.kind,
            result.attempt_number,
            result.status,
            result.error_code or "none",
        )
    return processed


async def run(args: argparse.Namespace) -> None:
    if not 1 <= args.max_items <= 1_000:
        raise ValueError("--max-items must be between 1 and 1000")
    settings = get_settings()
    if not settings.fulfillment_outbox_enabled:
        raise RuntimeError("FULFILLMENT_OUTBOX_ENABLED is required")
    if not (
        settings.fulfillment_email_enabled
        or settings.fulfillment_cdek_enabled
        or settings.fulfillment_crm_enabled
    ):
        raise RuntimeError(
            "FULFILLMENT_EMAIL_ENABLED, FULFILLMENT_CDEK_ENABLED, or "
            "FULFILLMENT_CRM_ENABLED is required"
        )
    poll_seconds = (
        args.poll_seconds
        if args.poll_seconds is not None
        else float(settings.fulfillment_poll_seconds)
    )
    if poll_seconds <= 0:
        raise ValueError("--poll-seconds must be positive")

    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    database = DatabaseManager(settings)
    await database.startup()
    try:
        while True:
            processed = await process_batch(
                database,
                max_items=args.max_items,
                worker_id=worker_id,
            )
            if args.once:
                return
            if processed == 0:
                await asyncio.sleep(poll_seconds)
    finally:
        await database.shutdown()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
