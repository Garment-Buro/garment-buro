from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.catalog.migration import (
    CatalogMigrationPlan,
    CatalogMigrationService,
    LegacyCatalogPlanner,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit or import the legacy SQLite catalog and local uploads",
    )
    parser.add_argument("--sqlite-db", type=Path, required=True)
    parser.add_argument("--uploads-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Upload media and insert into the configured empty target database",
    )
    parser.add_argument(
        "--expect-fingerprint",
        help="Required with --apply; must equal the reviewed dry-run fingerprint",
    )
    return parser.parse_args()


async def apply_plan(plan: CatalogMigrationPlan) -> dict[str, object]:
    settings = get_settings()
    if not settings.database_enabled or not settings.minio_enabled:
        raise RuntimeError("DATABASE_ENABLED and MINIO_ENABLED are required for --apply")

    database = DatabaseManager(settings)
    storage = MinioStorage(settings)
    await database.startup()
    try:
        await storage.startup()
        try:
            async with database.session() as session:
                result = await CatalogMigrationService(storage).apply(session, plan)
        finally:
            await storage.shutdown()
    finally:
        await database.shutdown()
    return {
        "applied": True,
        "fingerprint_sha256": result.fingerprint_sha256,
        "counts": {
            "products": result.products,
            "variants": result.variants,
            "media_assets": result.media_assets,
            "media_references": result.media_references,
        },
    }


def main() -> int:
    args = parse_args()
    plan = LegacyCatalogPlanner().build(args.sqlite_db, args.uploads_dir)
    report = plan.report()

    exit_code = 0 if plan.valid else 1
    if args.apply:
        if not plan.valid:
            report["apply_error"] = "Migration plan is invalid"
            exit_code = 2
        elif not args.expect_fingerprint:
            report["apply_error"] = "--expect-fingerprint is required with --apply"
            exit_code = 2
        elif args.expect_fingerprint != plan.fingerprint:
            report["apply_error"] = "Dry-run fingerprint does not match current source data"
            exit_code = 2
        else:
            report["apply_result"] = asyncio.run(apply_plan(plan))

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
