from __future__ import annotations

import argparse
import asyncio
import logging
import math
from collections import Counter
from datetime import datetime, timedelta, timezone

from minio.error import S3Error
from urllib3.exceptions import HTTPError

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.db.verification import verify_postgres_schema
from app.integrations.minio import MinioStorage
from app.modules.customer_projects.lifecycle import ProjectMediaReconciler
from app.modules.media.errors import PrivateStorageUnavailableError
from app.observability.logging import configure_logging

logger = logging.getLogger(__name__)


def positive_interval(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 876000:
        raise argparse.ArgumentTypeError("interval must be finite, positive and at most 876000")
    return number


def batch_size(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 1000:
        raise argparse.ArgumentTypeError("batch size must be between 1 and 1000")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile private customer project files")
    parser.add_argument("--once", action="store_true", help="Process one bounded batch and exit")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report candidates without changes; implies once"
    )
    parser.add_argument("--max-items", type=batch_size, default=100)
    parser.add_argument("--poll-seconds", type=positive_interval, default=60)
    parser.add_argument("--retry-seconds", type=positive_interval, default=60)
    parser.add_argument("--stale-upload-hours", type=positive_interval, default=1)
    parser.add_argument("--unattached-hours", type=positive_interval, default=168)
    return parser.parse_args()


async def process_batch(
    database: DatabaseManager, worker: ProjectMediaReconciler, *, max_items: int, dry_run: bool
) -> dict[str, int]:
    async with database.session() as session:
        projects, favorites, public_profiles = await worker.purge_deleted_data(
            session, limit=max_items, dry_run=dry_run
        )
    counts = Counter(
        {"projects": projects, "favorites": favorites, "public_profiles": public_profiles}
    )
    async with database.session() as session:
        detached_media = await worker.prune_design_assets(
            session, now=datetime.now(timezone.utc), limit=max_items, dry_run=dry_run
        )
    if detached_media:
        counts["design_media"] = detached_media
    async with database.session() as session:
        candidate_ids = await worker.candidate_ids(
            session, now=datetime.now(timezone.utc), limit=max_items
        )
    # Discover at most one batch. An old referenced archive is checked once per
    # batch, rather than rescanned for every successful storage deletion.
    for media_id in candidate_ids:
        async with database.session() as session:
            result = await worker.process_once(
                session, now=datetime.now(timezone.utc), dry_run=dry_run, candidate_id=media_id
            )
        if result is None:
            continue
        counts[result.status] += 1
    return dict(counts)


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    if (
        not settings.database_enabled
        or not settings.minio_enabled
        or not (settings.identity_api_enabled or settings.carts_v2_enabled)
    ):
        raise RuntimeError("Customer media cleanup requires database, MinIO and customer/cart API")
    database = DatabaseManager(settings)
    storage = MinioStorage(settings)
    worker = ProjectMediaReconciler(
        storage,
        stale_upload_age=timedelta(hours=args.stale_upload_hours),
        unattached_age=timedelta(hours=args.unattached_hours),
        retry_delay=timedelta(seconds=args.retry_seconds),
    )
    await database.startup()
    try:
        await verify_postgres_schema(database)
        await storage.startup()
        while True:
            try:
                counts = await process_batch(
                    database, worker, max_items=args.max_items, dry_run=args.dry_run
                )
                logger.info(
                    "Project media cleanup batch",
                    extra={
                        "event": "project_media.cleanup",
                        "component": "customer_projects",
                        "dry_run": args.dry_run,
                        "cleanup_counts": counts,
                    },
                )
            except (HTTPError, OSError, S3Error, PrivateStorageUnavailableError) as error:
                logger.warning(
                    "Project cleanup storage unavailable",
                    extra={"error_type": type(error).__name__},
                )
                if args.once or args.dry_run:
                    raise RuntimeError("Project cleanup storage unavailable") from None
            if args.once or args.dry_run:
                return
            # Always pause: a large backlog must not occupy all database/storage capacity.
            await asyncio.sleep(args.poll_seconds)
    finally:
        await storage.shutdown()
        await database.shutdown()


def main() -> None:
    args = parse_args()
    configure_logging(get_settings())
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
