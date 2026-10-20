"""Full cart/checkout HTTP transactions with PostgreSQL and real private MinIO."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url, text, update
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.factory import create_app
from app.integrations.minio import MinioStorage
from app.modules.customer_projects.lifecycle import ProjectMediaReconciler
from app.modules.design_assets.repository import DesignAssetRepository
from app.modules.media.models import MediaObject
from scripts.reconcile_project_media import process_batch
from tests.contract.test_checkout_api import _settings
from tests.contract.test_design_media_checkout import exercise_retention, exercise_rollback
from tests.integration.test_project_media_minio import real_storage as real_storage
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("MINIO_TEST_CONFIG_PATH") or not os.getenv("SCHEMA_TEST_POSTGRES_URL"),
    reason="Requires disposable PostgreSQL and MinIO",
)


@pytest.fixture
def checkout_storage(tmp_path, postgres_url, real_storage):
    source = make_url(postgres_url)
    name = "test_design_checkout_" + uuid4().hex
    url = source.set(database=name).render_as_string(hide_password=False)

    async def manage(action):
        engine = create_async_engine(source, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                await connection.execute(
                    text(
                        f'{action} DATABASE "{name}"'
                        + (" WITH (FORCE)" if action == "DROP" else "")
                    )
                )
        finally:
            await engine.dispose()

    asyncio.run(manage("CREATE"))
    try:
        migrate(url, "upgrade", "head")
        config, sdk, prefix, public_base = real_storage
        settings = Settings(
            _env_file=None,
            **{
                **_settings(tmp_path / "unused.db").model_dump(),
                "database_url": url,
                "minio_endpoint": config["endpoint"],
                "minio_access_key": config["access_key"],
                "minio_secret_key": config["secret_key"],
                "minio_bucket_prefix": prefix,
                "minio_public_base_url": public_base,
            },
        )
        yield settings, sdk
    finally:
        asyncio.run(manage("DROP"))


@pytest.mark.parametrize("outcome", ["success", "timeout"])
def test_real_checkout_retains_files_after_cart_clear_and_payment_response(
    tmp_path, checkout_storage, outcome
):
    settings, sdk = checkout_storage
    settings, path = exercise_retention(tmp_path, settings=settings, sdk=sdk, outcome=outcome)

    async def reconcile():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                # Move the file past grace periods; the accepted order must be
                # the reason it survives, rather than its recent upload time.
                await session.execute(
                    update(MediaObject).values(
                        updated_at=datetime.now(timezone.utc) - timedelta(days=100)
                    )
                )
                await session.commit()
                assert (
                    await DesignAssetRepository().prune_expired(
                        session, now=datetime.now(timezone.utc) + timedelta(days=365)
                    )
                    == []
                )
                await session.commit()
            counts = await process_batch(
                database,
                ProjectMediaReconciler(MinioStorage(settings, client=sdk)),
                max_items=10,
                dry_run=False,
            )
            assert counts.get("deleted", 0) == 0
        finally:
            await database.shutdown()

    asyncio.run(reconcile())
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(path).status_code == 200


def test_actual_stock_failure_rolls_back_file_links_and_permanent_retention(
    tmp_path, checkout_storage
):
    settings, sdk = checkout_storage
    exercise_rollback(tmp_path, settings=settings, sdk=sdk)
