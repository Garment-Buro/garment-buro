from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.migration import (
    CatalogContractComparator,
    CatalogMigrationService,
    LegacyCatalogPlanner,
)
from app.modules.catalog.service import CatalogService


@dataclass(frozen=True, slots=True)
class VerificationWriteResult:
    etag: str
    version_id: str | None = None


class VerificationMinioClient:
    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str,
    ) -> VerificationWriteResult:
        payload = data.read()
        if len(payload) != length:
            raise RuntimeError(f"Short verification write for {object_name}")
        return VerificationWriteResult(etag=hashlib.sha256(payload).hexdigest())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare legacy catalog values with the refactored read path",
    )
    parser.add_argument("--sqlite-db", type=Path, required=True)
    parser.add_argument("--uploads-dir", type=Path, required=True)
    return parser.parse_args()


async def compare(database_path: Path, uploads_path: Path) -> dict[str, object]:
    plan = LegacyCatalogPlanner().build(database_path, uploads_path)
    if not plan.valid:
        return {
            "plan": plan.report(),
            "comparison": {
                "matches": False,
                "mismatches": ["Migration plan is invalid"],
            },
        }

    with tempfile.TemporaryDirectory(prefix="garment-catalog-compare-") as directory:
        target_path = Path(directory) / "target.db"
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{target_path}",
            minio_enabled=True,
            minio_access_key="contract-verification",
            minio_secret_key="contract-verification",
            minio_public_base_url="https://storage.invalid",
        )
        database = DatabaseManager(settings)
        storage = MinioStorage(settings, client=VerificationMinioClient())
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                migration = await CatalogMigrationService(storage).apply(session, plan)
            async with database.session() as session:
                comparison = await CatalogContractComparator(
                    CatalogService(CatalogResponseMapper(settings))
                ).compare(session, plan)
        finally:
            await database.shutdown()

    return {
        "plan": {
            "valid": plan.valid,
            "fingerprint_sha256": plan.fingerprint,
            "counts": plan.report()["counts"],
        },
        "migration": {
            "products": migration.products,
            "variants": migration.variants,
            "media_assets": migration.media_assets,
            "media_references": migration.media_references,
        },
        "comparison": comparison.report(),
    }


def main() -> int:
    args = parse_args()
    report = asyncio.run(compare(args.sqlite_db, args.uploads_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    comparison = report["comparison"]
    return 0 if isinstance(comparison, dict) and comparison.get("matches") else 1


if __name__ == "__main__":
    raise SystemExit(main())
