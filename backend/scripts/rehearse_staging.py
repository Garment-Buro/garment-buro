from __future__ import annotations

import argparse
import asyncio
import json

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import AppEnvironment, get_settings
from app.core.rehearsal import StagingRehearsalService
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run safe PostgreSQL/MinIO preflight checks for a reviewed release",
    )
    parser.add_argument(
        "--expect-environment",
        choices=[AppEnvironment.STAGING.value, AppEnvironment.PRODUCTION.value],
        default=AppEnvironment.STAGING.value,
    )
    parser.add_argument("--require-crm-writes", action="store_true")
    parser.add_argument("--require-crm-files", action="store_true")
    parser.add_argument("--require-database-tls", action="store_true")
    parser.add_argument("--storage-roundtrip", action="store_true")
    parser.add_argument("--allow-production-storage-roundtrip", action="store_true")
    return parser.parse_args()


def get_schema_head() -> str:
    heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
    if len(heads) != 1:
        raise RuntimeError("Alembic must have exactly one schema head")
    return heads[0]


async def run(args: argparse.Namespace) -> dict[str, object]:
    expected_environment = AppEnvironment(args.expect_environment)
    if (
        expected_environment is AppEnvironment.PRODUCTION
        and args.storage_roundtrip
        and not args.allow_production_storage_roundtrip
    ):
        raise RuntimeError(
            "Production storage roundtrip requires --allow-production-storage-roundtrip"
        )
    settings = get_settings()
    database = DatabaseManager(settings)
    storage = MinioStorage(settings)
    await database.startup()
    await storage.startup()
    try:
        async with database.session() as session:
            report = await StagingRehearsalService().inspect(
                session,
                settings=settings,
                storage=storage,
                expected_environment=expected_environment,
                expected_schema_head=get_schema_head(),
                require_crm_writes=args.require_crm_writes,
                require_crm_files=args.require_crm_files,
                require_database_tls=args.require_database_tls,
                storage_roundtrip=args.storage_roundtrip,
            )
            return report.to_dict()
    finally:
        await storage.shutdown()
        await database.shutdown()


def main() -> int:
    args = parse_args()
    try:
        report = asyncio.run(run(args))
    except Exception:  # noqa: BLE001 - operator output must never render DSNs or credentials.
        print(
            json.dumps(
                {"error": "Staging rehearsal preflight failed"},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("healthy") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
