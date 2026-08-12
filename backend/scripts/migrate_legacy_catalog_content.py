from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.catalog.content import (
    CatalogContentError,
    CatalogContentMigrationService,
    CatalogContentPlan,
    LegacyCatalogContentPlanner,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit or import legacy catalog settings and variant options",
    )
    parser.add_argument("--uploads-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--expect-fingerprint",
        help="Required with --apply; must equal the reviewed dry-run fingerprint",
    )
    return parser.parse_args()


async def apply_plan(plan: CatalogContentPlan) -> dict[str, object]:
    settings = get_settings()
    if not settings.database_enabled:
        raise CatalogContentError("DATABASE_ENABLED is required for --apply")
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            result = await CatalogContentMigrationService().apply(session, plan)
            await session.commit()
    finally:
        await database.shutdown()
    return {
        "applied": True,
        "fingerprint_sha256": result.fingerprint_sha256,
        "documents": result.documents,
    }


def main() -> int:
    args = parse_args()
    try:
        plan = LegacyCatalogContentPlanner().build(args.uploads_dir)
        report = plan.report()
        exit_code = 0
        if args.apply:
            if not args.expect_fingerprint:
                report["apply_error"] = "--expect-fingerprint is required with --apply"
                exit_code = 2
            elif args.expect_fingerprint != plan.fingerprint:
                report["apply_error"] = "Dry-run fingerprint does not match current source data"
                exit_code = 2
            else:
                report["apply_result"] = asyncio.run(apply_plan(plan))
    except CatalogContentError as error:
        report = {"valid": False, "error": str(error)}
        exit_code = 1

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
