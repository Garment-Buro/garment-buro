from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.crm.reconciliation import (
    CrmReconciliationService,
    CrmReconciliationStorageError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a read-only consistency inspection of target CRM data",
    )
    parser.add_argument("--verify-objects", action="store_true")
    parser.add_argument("--max-issues", type=int, default=1_000)
    parser.add_argument("--stale-after-seconds", type=int, default=900)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    if not settings.database_enabled:
        raise RuntimeError("DATABASE_ENABLED is required for CRM reconciliation")
    if args.verify_objects and not settings.minio_enabled:
        raise RuntimeError("MINIO_ENABLED is required with --verify-objects")
    database = DatabaseManager(settings)
    storage = MinioStorage(settings) if args.verify_objects else None
    await database.startup()
    try:
        if storage is not None:
            await storage.startup()
        try:
            async with database.session() as session:
                report = await CrmReconciliationService().inspect(
                    session,
                    private_bucket=settings.minio_crm_bucket,
                    storage=storage,
                    max_issues=args.max_issues,
                    stale_after_seconds=args.stale_after_seconds,
                )
                return report.to_dict()
        finally:
            if storage is not None:
                await storage.shutdown()
    finally:
        await database.shutdown()


def main() -> int:
    args = parse_args()
    try:
        report = asyncio.run(run(args))
    except SQLAlchemyError:
        print(
            json.dumps(
                {"error": "CRM reconciliation database inspection failed"},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    except (CrmReconciliationStorageError, RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {"error": str(error)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("healthy") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
