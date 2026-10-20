"""Private file deletion is exercised against real PostgreSQL and MinIO."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import uuid4

import pytest
from minio.error import S3Error
from PIL import Image
from sqlalchemy import delete, event, func, insert, select, text

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.catalog.models import Product, ProductCategory
from app.modules.customer_projects.models import CustomerProject, CustomerProjectMedia
from app.modules.customer_projects.schemas import ProjectCreate
from app.modules.customer_projects.service import ProjectNotFoundError, ProjectService
from app.modules.favorites.models import UserFavorite
from app.modules.identity.models import User
from app.modules.media.models import MediaObject
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.integration.test_project_media_minio import real_storage  # noqa: F401
from tests.postgres_schema import migrate
from tests.projects_scenario import project_payload

pytestmark = pytest.mark.skipif(
    not os.getenv("MINIO_TEST_CONFIG_PATH") or not os.getenv("SCHEMA_TEST_POSTGRES_URL"),
    reason="Requires isolated real PostgreSQL and MinIO",
)


@pytest.fixture
def lifecycle_env(postgres_url, real_storage):  # noqa: F811
    config, sdk, prefix, public_base = real_storage
    migrate(postgres_url, "upgrade", "head")
    base = favorite_settings(postgres_url)
    settings = Settings(
        _env_file=None,
        **{
            **base.model_dump(),
            "minio_enabled": True,
            "minio_endpoint": config["endpoint"],
            "minio_access_key": config["access_key"],
            "minio_secret_key": config["secret_key"],
            "minio_bucket_prefix": prefix,
            "minio_public_base_url": public_base,
        },
    )
    products, _, users = asyncio.run(seed_favorites(settings, create_schema=False))
    try:
        yield settings, sdk, products, users
    finally:

        async def cleanup():
            database = DatabaseManager(settings)
            await database.startup()
            try:
                async with database.session() as session:
                    categories = list(
                        await session.scalars(
                            select(Product.category_id).where(
                                Product.id.in_(products), Product.category_id.is_not(None)
                            )
                        )
                    )
                    await session.execute(delete(User).where(User.id.in_(users)))
                    await session.execute(delete(Product).where(Product.id.in_(products)))
                    await session.execute(
                        delete(MediaObject).where(
                            MediaObject.bucket_name.in_(
                                [
                                    settings.minio_customer_projects_bucket,
                                    settings.minio_media_bucket,
                                    settings.minio_crm_bucket,
                                ]
                            )
                        )
                    )
                    await session.execute(
                        delete(ProductCategory).where(ProductCategory.id.in_(categories))
                    )
                    await session.commit()
            finally:
                await database.shutdown()

        asyncio.run(cleanup())


def image_bytes():
    data = BytesIO()
    Image.new("RGBA", (4, 4), (20, 40, 60, 128)).save(data, format="WEBP", lossless=True)
    return data.getvalue()


async def add_media(
    session,
    settings,
    sdk,
    owner,
    *,
    status="ready",
    age=timedelta(days=8),
    bucket=None,
    public=False,
    key=None,
):
    data = image_bytes()
    bucket = bucket or settings.minio_customer_projects_bucket
    key = key or f"projects/{owner}/{uuid4().hex}.webp"
    sdk.put_object(bucket, key, BytesIO(data), len(data), content_type="image/webp")
    media = MediaObject(
        uploaded_by_user_id=owner,
        bucket_name=bucket,
        object_key=key,
        content_type="image/webp",
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
        status=status,
        is_public=public,
        created_at=datetime.now(timezone.utc) - age,
        updated_at=datetime.now(timezone.utc) - age,
    )
    session.add(media)
    await session.flush()
    return media


def test_reconciler_deletes_only_expired_unattached_private_files(lifecycle_env):
    settings, sdk, products, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler

        database = DatabaseManager(settings)
        await database.startup()
        storage = MinioStorage(settings, client=sdk)
        worker = ProjectMediaReconciler(storage)
        try:
            async with database.session() as session:
                old = [
                    await add_media(session, settings, sdk, users[0], status=status)
                    for status in ("ready", "pending", "failed", "deleted")
                ]
                keep = [
                    await add_media(session, settings, sdk, users[0], **options)
                    for options in (
                        {"age": timedelta(minutes=1)},
                        {"status": "pending", "age": timedelta(minutes=1)},
                        {"public": True},
                        {"bucket": settings.minio_crm_bucket},
                        {"key": "outside/never-remove.webp"},
                    )
                ]
                linked = await add_media(session, settings, sdk, users[0])
                project = CustomerProject(
                    user_id=users[0],
                    product_id=products[0],
                    client_key="kept",
                    creation_sha256="a" * 64,
                    kind="draft",
                    title="Active project",
                    version=1,
                    snapshot=project_payload(products[0], linked.id)["snapshot"],
                )
                session.add(project)
                await session.flush()
                session.add(CustomerProjectMedia(project_id=project.id, media_object_id=linked.id))
                await session.commit()
            removed = []
            for _ in range(10):
                async with database.session() as session:
                    result = await worker.process_once(session, now=datetime.now(timezone.utc))
                if result is None:
                    break
                assert result.status == "deleted"
                removed.append(result.media_id)
            assert set(removed) == {media.id for media in old}
            async with database.session() as session:
                for media in old:
                    assert await session.get(MediaObject, media.id) is None
                    with pytest.raises(S3Error) as missing:
                        sdk.stat_object(media.bucket_name, media.object_key)
                    assert missing.value.code == "NoSuchKey"
                for media in [*keep, linked]:
                    assert (await session.get(MediaObject, media.id)).status == media.status
                    assert sdk.stat_object(media.bucket_name, media.object_key).size > 0
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_failed_remove_keeps_durable_retry_and_second_worker_finishes(lifecycle_env, monkeypatch):
    settings, sdk, _, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler

        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                media = await add_media(session, settings, sdk, users[0])
                await session.commit()
            original = sdk.remove_object

            def fail(*args, **kwargs):
                raise OSError("temporary storage outage")

            monkeypatch.setattr(sdk, "remove_object", fail)
            worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
            now = datetime.now(timezone.utc)
            async with database.session() as session:
                result = await worker.process_once(session, now=now)
                assert result.status == "retry"
            async with database.session() as session:
                assert (await session.get(MediaObject, media.id)).status == "deleted"
                assert await worker.process_once(session, now=now) is None
            assert sdk.stat_object(media.bucket_name, media.object_key).size > 0
            monkeypatch.setattr(sdk, "remove_object", original)
            restarted = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
            async with database.session() as session:
                assert (
                    await restarted.process_once(session, now=now + timedelta(minutes=2))
                ).status == "deleted"
            async with database.session() as session:
                assert await session.get(MediaObject, media.id) is None
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_deleted_account_is_purged_in_bounded_batches_and_cannot_write(lifecycle_env):
    settings, sdk, products, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler

        database = DatabaseManager(settings)
        await database.startup()
        worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
        try:
            async with database.session() as session:
                media = await add_media(session, settings, sdk, users[0], age=timedelta(minutes=1))
                for key in ("first", "second"):
                    project = CustomerProject(
                        user_id=users[0],
                        product_id=products[0],
                        client_key=key,
                        creation_sha256="a" * 64,
                        kind="draft",
                        title="Deleted account",
                        version=1,
                        snapshot=project_payload(products[0], media.id)["snapshot"],
                    )
                    session.add(project)
                    await session.flush()
                    session.add(
                        CustomerProjectMedia(project_id=project.id, media_object_id=media.id)
                    )
                session.add(UserFavorite(user_id=users[0], product_id=products[0]))
                (await session.get(User, users[0])).status = "deleted"
                await session.commit()
            async with database.session() as session:
                with pytest.raises(ProjectNotFoundError):
                    await ProjectService(settings).create(
                        session,
                        user_id=users[0],
                        payload=ProjectCreate.model_validate(
                            project_payload(products[0], media.id, key="late-request")
                        ),
                    )
                await session.rollback()
            async with database.session() as session:
                assert await worker.purge_deleted_data(session, limit=1) == (1, 1, 0)
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(CustomerProject)
                        .where(CustomerProject.user_id == users[0])
                    )
                    == 1
                )
                assert await worker.process_once(session, now=datetime.now(timezone.utc)) is None
            async with database.session() as session:
                assert await worker.purge_deleted_data(session, limit=1) == (1, 0, 0)
            async with database.session() as session:
                assert (
                    await worker.process_once(session, now=datetime.now(timezone.utc))
                ).status == "deleted"
                assert await session.get(MediaObject, media.id) is None
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(UserFavorite)
                        .where(UserFavorite.user_id == users[0])
                    )
                    == 0
                )
                assert (await session.get(User, users[1])).status == "active"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_inflight_project_attachment_prevents_cleanup(lifecycle_env):
    settings, sdk, products, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler

        database = DatabaseManager(settings)
        await database.startup()
        worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
        try:
            async with database.session() as session:
                media = await add_media(session, settings, sdk, users[0])
                await session.commit()
            async with database.session() as saving:
                result, _ = await ProjectService(settings).create(
                    saving,
                    user_id=users[0],
                    payload=ProjectCreate.model_validate(project_payload(products[0], media.id)),
                )
                async with database.session() as cleaning:
                    assert (
                        await asyncio.wait_for(
                            worker.process_once(cleaning, now=datetime.now(timezone.utc)), timeout=3
                        )
                        is None
                    )
                await saving.commit()
            async with database.session() as cleaning:
                assert await worker.process_once(cleaning, now=datetime.now(timezone.utc)) is None
                assert (await cleaning.get(CustomerProject, result.id)).snapshot is not None
                assert sdk.stat_object(media.bucket_name, media.object_key).size > 0
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_inflight_upload_cannot_be_deleted_then_resurrected(lifecycle_env, monkeypatch):
    settings, sdk, _, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler
        from app.modules.customer_projects.media_service import ProjectMediaService

        database = DatabaseManager(settings)
        await database.startup()
        worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
        entered, release = threading.Event(), threading.Event()
        original = sdk.put_object

        def delayed_put(*args, **kwargs):
            entered.set()
            assert release.wait(timeout=10)
            return original(*args, **kwargs)

        monkeypatch.setattr(sdk, "put_object", delayed_put)

        async def upload():
            async with database.session() as session:
                return await ProjectMediaService(MinioStorage(settings, client=sdk)).upload(
                    session, user_id=users[0], data=image_bytes(), original_filename="image.webp"
                )

        task = asyncio.create_task(upload())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            async with database.session() as cleaning:
                assert (
                    await asyncio.wait_for(
                        worker.process_once(
                            cleaning, now=datetime.now(timezone.utc) + timedelta(hours=2)
                        ),
                        timeout=3,
                    )
                    is None
                )
            release.set()
            result = await asyncio.wait_for(task, timeout=5)
            async with database.session() as session:
                media = await session.get(MediaObject, result.id)
                assert media.status == "ready"
                assert sdk.stat_object(media.bucket_name, media.object_key).size > 0
        finally:
            release.set()
            if not task.done():
                await task
            await database.shutdown()

    asyncio.run(scenario())


def test_dry_run_entrypoint_reports_distinct_candidates_without_changes(
    lifecycle_env, monkeypatch, caplog
):
    settings, sdk, _, users = lifecycle_env

    async def scenario():
        from app.observability.logging import JsonFormatter
        from scripts import reconcile_project_media

        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                media = [await add_media(session, settings, sdk, users[0]) for _ in range(3)]
                await session.commit()
            monkeypatch.setattr(reconcile_project_media, "get_settings", lambda: settings)
            await reconcile_project_media.run(
                Namespace(
                    once=True,
                    dry_run=True,
                    max_items=2,
                    poll_seconds=60,
                    retry_seconds=60,
                    stale_upload_hours=1,
                    unattached_hours=168,
                )
            )
            event = next(
                record
                for record in caplog.records
                if record.name == "scripts.reconcile_project_media"
            )
            payload = json.loads(JsonFormatter().format(event))
            assert payload["cleanup_counts"] == {
                "projects": 0,
                "favorites": 0,
                "public_profiles": 0,
                "candidate": 2,
            }
            assert payload["dry_run"] is True
            async with database.session() as session:
                for item in media:
                    assert (await session.get(MediaObject, item.id)).status == "ready"
                    assert sdk.stat_object(item.bucket_name, item.object_key).size > 0
        finally:
            await database.shutdown()

    with caplog.at_level(logging.INFO):
        asyncio.run(scenario())


def test_detached_image_receives_full_retention_period(lifecycle_env):
    settings, sdk, products, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler

        database = DatabaseManager(settings)
        await database.startup()
        worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
        try:
            async with database.session() as session:
                media = await add_media(session, settings, sdk, users[0], age=timedelta(days=100))
                project, _ = await ProjectService(settings).create(
                    session,
                    user_id=users[0],
                    payload=ProjectCreate.model_validate(project_payload(products[0], media.id)),
                )
                await session.commit()
            async with database.session() as session:
                await ProjectService(settings).remove(
                    session, user_id=users[0], project_id=project.id, expected_version=1
                )
                await session.commit()
            async with database.session() as session:
                now = datetime.now(timezone.utc)
                assert await worker.process_once(session, now=now + timedelta(days=6)) is None
                assert (
                    await worker.process_once(session, now=now + timedelta(days=8))
                ).status == "deleted"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


@pytest.mark.parametrize("prefetched", [False, True])
def test_worker_lock_and_committed_tombstone_both_reject_attachment(lifecycle_env, prefetched):
    settings, sdk, products, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler
        from app.modules.customer_projects.service import ProjectMediaError

        database = DatabaseManager(settings)
        await database.startup()
        worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
        try:
            async with database.session() as session:
                media = await add_media(session, settings, sdk, users[0])
                await session.commit()
            if prefetched:
                async with database.session() as session:
                    assert await worker.candidate_ids(
                        session, now=datetime.now(timezone.utc), limit=10
                    ) == [media.id]
            async with database.session() as first:
                await first.scalar(
                    select(MediaObject).where(MediaObject.id == media.id).with_for_update()
                )
                async with database.session() as second:
                    assert (
                        await asyncio.wait_for(
                            worker.process_once(
                                second,
                                now=datetime.now(timezone.utc),
                                candidate_id=media.id if prefetched else None,
                            ),
                            timeout=3,
                        )
                        is None
                    )
                (await first.get(MediaObject, media.id)).status = "deleted"
                await first.commit()
            async with database.session() as saving:
                with pytest.raises(ProjectMediaError):
                    await ProjectService(settings).create(
                        saving,
                        user_id=users[0],
                        payload=ProjectCreate.model_validate(
                            project_payload(products[0], media.id)
                        ),
                    )
                await saving.rollback()
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_prefetched_candidate_rechecks_new_attachment_and_detach_grace(lifecycle_env):
    settings, sdk, products, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler

        database = DatabaseManager(settings)
        await database.startup()
        worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
        try:
            async with database.session() as session:
                media = await add_media(session, settings, sdk, users[0])
                await session.commit()
            async with database.session() as session:
                assert await worker.candidate_ids(
                    session, now=datetime.now(timezone.utc), limit=10
                ) == [media.id]
            async with database.session() as session:
                project, _ = await ProjectService(settings).create(
                    session,
                    user_id=users[0],
                    payload=ProjectCreate.model_validate(project_payload(products[0], media.id)),
                )
                await session.commit()
            async with database.session() as session:
                assert (
                    await worker.process_once(
                        session, now=datetime.now(timezone.utc), candidate_id=media.id
                    )
                    is None
                )
            async with database.session() as session:
                await ProjectService(settings).remove(
                    session, user_id=users[0], project_id=project.id, expected_version=1
                )
                await session.commit()
            async with database.session() as session:
                assert (
                    await worker.process_once(
                        session, now=datetime.now(timezone.utc), candidate_id=media.id
                    )
                    is None
                )
                assert sdk.stat_object(media.bucket_name, media.object_key).size > 0
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_prefetched_candidate_rechecks_age_after_lock_snapshot_changes(lifecycle_env):
    settings, sdk, products, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler

        database = DatabaseManager(settings)
        await database.startup()
        worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
        lock_key = int(uuid4().hex[:7], 16)
        paused = False
        task = None

        def barrier(connection, cursor, statement, parameters, context, executemany):
            nonlocal paused
            if (
                not paused
                and statement.lstrip().startswith("SELECT")
                and "FROM media_objects" in statement
                and "FOR UPDATE" in statement
            ):
                paused = True
                statement = (
                    f"WITH lifecycle_barrier AS MATERIALIZED (SELECT pg_advisory_xact_lock({lock_key})) "
                    + statement.replace(
                        "WHERE ", "WHERE (SELECT count(*) = 1 FROM lifecycle_barrier) AND ", 1
                    )
                )
            return statement, parameters

        try:
            async with database.session() as session:
                media = await add_media(session, settings, sdk, users[0])
                await session.commit()
            async with database.session() as blocker:
                await blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
                event.listen(
                    database.engine.sync_engine, "before_cursor_execute", barrier, retval=True
                )

                async def clean():
                    async with database.session() as session:
                        return await worker.process_once(
                            session, now=datetime.now(timezone.utc), candidate_id=media.id
                        )

                task = asyncio.create_task(clean())
                try:
                    async with database.session() as observer:
                        for _ in range(100):
                            waiting = await observer.scalar(
                                text(
                                    "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND objid = :key AND NOT granted)"
                                ),
                                {"key": lock_key},
                            )
                            if waiting:
                                break
                            await asyncio.sleep(0.02)
                        assert waiting, "Worker must be paused after its statement snapshot"
                    # Actual attach+detach commits a new retention window while
                    # the cleaner still holds the earlier statement snapshot.
                    async with database.session() as saving:
                        project, _ = await ProjectService(settings).create(
                            saving,
                            user_id=users[0],
                            payload=ProjectCreate.model_validate(
                                project_payload(products[0], media.id)
                            ),
                        )
                        await ProjectService(settings).remove(
                            saving, user_id=users[0], project_id=project.id, expected_version=1
                        )
                        await saving.commit()
                finally:
                    await blocker.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key}
                    )
                assert await asyncio.wait_for(task, timeout=5) is None
            async with database.session() as session:
                assert (await session.get(MediaObject, media.id)).status == "ready"
                assert sdk.stat_object(media.bucket_name, media.object_key).size > 0
        finally:
            event.remove(database.engine.sync_engine, "before_cursor_execute", barrier)
            if task and not task.done():
                await task
            await database.shutdown()

    asyncio.run(scenario())


def test_cleanup_physically_removes_versions_and_delete_markers(lifecycle_env):
    settings, sdk, _, users = lifecycle_env

    async def scenario():
        from minio.versioningconfig import ENABLED, VersioningConfig

        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler

        database = DatabaseManager(settings)
        await database.startup()
        bucket = settings.minio_customer_projects_bucket
        sdk.set_bucket_versioning(bucket, VersioningConfig(ENABLED))
        try:
            async with database.session() as session:
                media = await add_media(session, settings, sdk, users[0])
                await session.commit()
            data = image_bytes()
            sdk.put_object(
                bucket, media.object_key, BytesIO(data), len(data), content_type="image/webp"
            )
            sdk.remove_object(bucket, media.object_key)
            assert (
                len(list(sdk.list_objects(bucket, prefix=media.object_key, include_version=True)))
                == 3
            )
            worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
            async with database.session() as session:
                assert (
                    await worker.process_once(session, now=datetime.now(timezone.utc))
                ).status == "deleted"
            assert (
                list(sdk.list_objects(bucket, prefix=media.object_key, include_version=True)) == []
            )
        finally:
            # Test cleanup owns the entire disposable bucket, including versions.
            for item in sdk.list_objects(bucket, recursive=True, include_version=True):
                sdk.remove_object(bucket, item.object_name, version_id=item.version_id)
            await database.shutdown()

    asyncio.run(scenario())


def test_crm_photo_reference_is_preserved_even_with_set_null_fk(lifecycle_env):
    settings, sdk, _, users = lifecycle_env

    async def scenario():
        from app.modules.crm.assortment_models import CrmAccessory, CrmAccessoryCategory
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler

        database = DatabaseManager(settings)
        await database.startup()
        accessory_id = category_id = None
        try:
            async with database.session() as session:
                media = await add_media(session, settings, sdk, users[0])
                category = CrmAccessoryCategory(code=uuid4().hex, name="Test category")
                session.add(category)
                await session.flush()
                accessory = CrmAccessory(
                    category_id=category.id,
                    code=uuid4().hex,
                    name="Test photo",
                    photo_media_object_id=media.id,
                )
                session.add(accessory)
                await session.flush()
                accessory_id, category_id = accessory.id, category.id
                await session.commit()
            worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
            async with database.session() as session:
                assert await worker.process_once(session, now=datetime.now(timezone.utc)) is None
                assert (
                    await session.get(CrmAccessory, accessory_id)
                ).photo_media_object_id == media.id
                assert sdk.stat_object(media.bucket_name, media.object_key).size > 0
        finally:
            async with database.session() as session:
                if accessory_id:
                    await session.execute(
                        delete(CrmAccessory).where(CrmAccessory.id == accessory_id)
                    )
                if category_id:
                    await session.execute(
                        delete(CrmAccessoryCategory).where(CrmAccessoryCategory.id == category_id)
                    )
                await session.commit()
            await database.shutdown()

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel_count", [1, 3])
def test_cancelled_upload_keeps_lock_until_sdk_put_finishes(
    lifecycle_env, monkeypatch, cancel_count
):
    settings, sdk, _, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler
        from app.modules.customer_projects.media_service import ProjectMediaService

        database = DatabaseManager(settings)
        await database.startup()
        entered, release = threading.Event(), threading.Event()
        original = sdk.put_object

        def delayed_put(*args, **kwargs):
            entered.set()
            assert release.wait(timeout=10)
            return original(*args, **kwargs)

        monkeypatch.setattr(sdk, "put_object", delayed_put)

        async def upload():
            async with database.session() as session:
                return await ProjectMediaService(MinioStorage(settings, client=sdk)).upload(
                    session, user_id=users[0], data=image_bytes(), original_filename="image.webp"
                )

        task = asyncio.create_task(upload())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            for _ in range(cancel_count):
                task.cancel()
                await asyncio.sleep(0.02)
                assert not task.done()
            worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
            async with database.session() as session:
                assert (
                    await asyncio.wait_for(
                        worker.process_once(
                            session, now=datetime.now(timezone.utc) + timedelta(hours=2)
                        ),
                        timeout=3,
                    )
                    is None
                )
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            async with database.session() as session:
                assert (
                    await worker.process_once(
                        session, now=datetime.now(timezone.utc) + timedelta(hours=2)
                    )
                ).status == "deleted"
        finally:
            release.set()
            if not task.done():
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            await database.shutdown()

    asyncio.run(scenario())


@pytest.mark.parametrize("has_expired", [True, False])
def test_cleanup_candidate_does_not_scan_thousands_of_fresh_uploads(lifecycle_env, has_expired):
    settings, _, _, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle_repository import ProjectLifecycleRepository

        database = DatabaseManager(settings)
        await database.startup()
        now = datetime.now(timezone.utc)
        try:
            async with database.session() as session:
                # This probe measures SQL only; no storage operation uses these rows.
                rows = [
                    {
                        "bucket_name": settings.minio_customer_projects_bucket,
                        "object_key": f"projects/{users[0]}/{uuid4().hex}.webp",
                        "content_type": "image/webp",
                        "size_bytes": 1,
                        "checksum_sha256": "a" * 64,
                        "status": "ready",
                        "is_public": False,
                        "uploaded_by_user_id": users[0],
                        "created_at": now,
                        "updated_at": now,
                    }
                    for _ in range(10000)
                ]
                if has_expired:
                    rows[-1]["updated_at"] = now - timedelta(days=8)
                await session.execute(insert(MediaObject), rows)
                await session.commit()
                await session.connection()
                await session.execute(text("ANALYZE media_objects"))
                await session.commit()
            queries = []

            def capture(connection, cursor, statement, parameters, context, executemany):
                if statement.lstrip().startswith("SELECT") and "FROM media_objects" in statement:
                    queries.append((statement, parameters))

            event.listen(database.engine.sync_engine, "before_cursor_execute", capture)
            try:
                async with database.session() as session:
                    candidate = await ProjectLifecycleRepository().next_candidate(
                        session,
                        bucket_name=settings.minio_customer_projects_bucket,
                        now=now,
                        stale_upload_age=timedelta(hours=1),
                        unattached_age=timedelta(days=7),
                        retry_delay=timedelta(minutes=1),
                    )
                    if has_expired:
                        assert candidate.object_key == rows[-1]["object_key"]
                    else:
                        assert candidate is None
                    await session.rollback()
            finally:
                event.remove(database.engine.sync_engine, "before_cursor_execute", capture)

            def discarded(node):
                return node.get("Rows Removed by Filter", 0) + sum(
                    discarded(child) for child in node.get("Plans", [])
                )

            async with database.session() as session:
                connection = await session.connection()
                for statement, parameters in queries:
                    result = await connection.exec_driver_sql(
                        "EXPLAIN (ANALYZE, FORMAT JSON) " + statement, parameters
                    )
                    plan = result.scalar_one()[0]["Plan"]
                    assert discarded(plan) < 100, {
                        "discarded_rows": discarded(plan),
                        "node": plan["Node Type"],
                    }
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cleanup_batch_does_not_rescan_referenced_archive_for_every_file(lifecycle_env):
    settings, sdk, products, users = lifecycle_env

    async def scenario():
        from app.modules.customer_projects.lifecycle import ProjectMediaReconciler
        from scripts.reconcile_project_media import process_batch

        database = DatabaseManager(settings)
        await database.startup()
        now = datetime.now(timezone.utc)
        try:
            async with database.session() as session:
                rows = [
                    {
                        "bucket_name": settings.minio_customer_projects_bucket,
                        "object_key": f"projects/{users[0]}/{uuid4().hex}.webp",
                        "content_type": "image/webp",
                        "size_bytes": 1,
                        "checksum_sha256": "a" * 64,
                        "status": "ready",
                        "is_public": False,
                        "uploaded_by_user_id": users[0],
                        "created_at": now - timedelta(days=20),
                        "updated_at": now - timedelta(days=20),
                    }
                    for _ in range(2000)
                ]
                media_ids = list(
                    await session.scalars(insert(MediaObject).returning(MediaObject.id), rows)
                )
                project = CustomerProject(
                    user_id=users[0],
                    product_id=products[0],
                    client_key="archive",
                    creation_sha256="a" * 64,
                    kind="draft",
                    title="Archive",
                    version=1,
                    snapshot=project_payload(products[0], media_ids[0])["snapshot"],
                )
                session.add(project)
                await session.flush()
                await session.execute(
                    insert(CustomerProjectMedia),
                    [
                        {"project_id": project.id, "media_object_id": media_id}
                        for media_id in media_ids
                    ],
                )
                expired = [await add_media(session, settings, sdk, users[0]) for _ in range(10)]
                await session.commit()
                await session.execute(text("ANALYZE media_objects"))
                await session.execute(text("ANALYZE customer_project_media"))
                await session.commit()
            queries = []

            def capture(connection, cursor, statement, parameters, context, executemany):
                if (
                    statement.lstrip().startswith("SELECT")
                    and "FROM media_objects" in statement
                    and "~" in statement
                ):
                    queries.append((statement, parameters))

            event.listen(database.engine.sync_engine, "before_cursor_execute", capture)
            try:
                counts = await process_batch(
                    database,
                    ProjectMediaReconciler(MinioStorage(settings, client=sdk)),
                    max_items=10,
                    dry_run=False,
                )
            finally:
                event.remove(database.engine.sync_engine, "before_cursor_execute", capture)
            assert counts == {"projects": 0, "favorites": 0, "public_profiles": 0, "deleted": 10}

            def discarded(node):
                return node.get("Rows Removed by Filter", 0) * node.get("Actual Loops", 1) + sum(
                    discarded(child) for child in node.get("Plans", [])
                )

            total_discarded = 0
            async with database.session() as session:
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(MediaObject)
                        .where(MediaObject.id.in_(media_ids))
                    )
                    == 2000
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(MediaObject)
                        .where(MediaObject.id.in_([item.id for item in expired]))
                    )
                    == 0
                )
                connection = await session.connection()
                for statement, parameters in queries:
                    result = await connection.exec_driver_sql(
                        "EXPLAIN (ANALYZE, FORMAT JSON) " + statement, parameters
                    )
                    total_discarded += discarded(result.scalar_one()[0]["Plan"])
            assert total_discarded < 5000, {
                "discarded_rows": total_discarded,
                "queries": len(queries),
            }
        finally:
            await database.shutdown()

    asyncio.run(scenario())
