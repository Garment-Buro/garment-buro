"""Required real PostgreSQL/MinIO photo access, concurrency and cleanup checks."""

import asyncio
import os
import threading
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from minio.error import S3Error
from PIL import Image
from sqlalchemy import delete, select, update

from app.core.config import Settings
from app.factory import create_app
from app.integrations.minio import MinioStorage
from app.modules.catalog.models import Product, ProductCategory
from app.modules.customer_projects.lifecycle import ProjectMediaReconciler
from app.modules.identity.models import User
from app.modules.media.models import MediaObject
from app.modules.public_profiles.avatar_service import AvatarService
from app.modules.public_profiles.models import PublicUserProfile
from app.modules.public_profiles.schemas import PublicProfileWrite
from app.modules.public_profiles.service import ProfileConflictError, PublicProfileService
from tests.contract.test_public_profile_media import (
    OWN,
    UPLOAD,
    create_profile,
    image_bytes,
    upload,
    write_body,
)
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.integration.test_project_media_minio import real_storage  # noqa: F401
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL") or not os.getenv("MINIO_TEST_CONFIG_PATH"),
    reason="Requires disposable real PostgreSQL and MinIO",
)


@pytest.fixture
def profile_storage(postgres_url, real_storage):  # noqa: F811
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
    products, tokens, users = asyncio.run(seed_favorites(settings, create_schema=False))
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        try:
            yield client, settings, sdk, tokens, users
        finally:

            async def clean():
                async with client.app.state.database.session() as session:
                    categories = list(
                        await session.scalars(
                            select(Product.category_id).where(Product.id.in_(products))
                        )
                    )
                    await session.execute(delete(User).where(User.id.in_(users)))
                    await session.execute(delete(Product).where(Product.id.in_(products)))
                    await session.execute(
                        delete(MediaObject).where(
                            MediaObject.bucket_name == settings.minio_customer_projects_bucket
                        )
                    )
                    await session.execute(
                        delete(ProductCategory).where(ProductCategory.id.in_(categories))
                    )
                    await session.commit()

            client.portal.call(clean)


def test_real_avatar_bytes_are_private_and_survive_application_restart(profile_storage):
    from urllib.error import HTTPError
    from urllib.request import urlopen

    client, settings, sdk, (owner, other), _ = profile_storage
    create_profile(client, owner, is_published=True)
    response = upload(client, owner)
    assert response.status_code == 201
    saved = response.json()
    public_url = f"/api/people/{saved['slug']}/avatar/{saved['avatar_id']}"
    public = client.get(public_url)
    assert public.status_code == 200 and public.headers["cache-control"] == "no-store"
    preview = client.get(public_url + "/preview")
    assert preview.status_code == 200 and preview.headers["cache-control"] == "no-store"
    with Image.open(BytesIO(preview.content)) as decoded:
        assert decoded.size == (320, 160)
    assert client.get(f"{UPLOAD}/{saved['avatar_id']}", headers=other).status_code == 404

    async def record():
        async with client.app.state.database.session() as session:
            return await session.get(MediaObject, saved["avatar_id"])

    media = client.portal.call(record)
    assert sdk.stat_object(media.bucket_name, media.object_key).size == len(public.content)
    with pytest.raises(HTTPError) as denied:
        urlopen(
            f"http://{settings.minio_endpoint}/{media.bucket_name}/{media.object_key}", timeout=5
        )
    assert denied.value.code == 403
    denied.value.close()
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(public_url).content == public.content
        assert restarted.get(public_url + "/preview").content == preview.content
    hidden = client.put(OWN, headers=owner, json=write_body(saved, is_published=False))
    assert hidden.status_code == 200
    assert client.get(public_url).status_code == 404
    assert client.get(public_url + "/preview").status_code == 404
    assert client.get(f"{UPLOAD}/{saved['avatar_id']}", headers=owner).content == public.content


def test_reference_retention_and_deleted_account_cleanup_use_real_storage(profile_storage):
    client, _, sdk, (owner, _), _ = profile_storage
    create_profile(client, owner, is_published=True)
    first = upload(client, owner).json()

    async def scenario():
        worker = ProjectMediaReconciler(client.app.state.storage)
        database = client.app.state.database
        now = datetime.now(timezone.utc)
        async with database.session() as session:
            await session.execute(
                update(MediaObject)
                .where(MediaObject.id == first["avatar_id"])
                .values(updated_at=now - timedelta(days=100))
            )
            await session.commit()
        async with database.session() as session:
            assert (
                await worker.process_once(
                    session, now=now + timedelta(days=10), candidate_id=first["avatar_id"]
                )
                is None
            )
        async with database.session() as session:
            return await session.get(MediaObject, first["avatar_id"])

    old_media = client.portal.call(scenario)
    replaced = upload(client, owner, version=2).json()

    async def retain_and_remove_old():
        worker = ProjectMediaReconciler(client.app.state.storage)
        now = datetime.now(timezone.utc)
        async with client.app.state.database.session() as session:
            assert (
                await worker.process_once(
                    session, now=now + timedelta(days=6), candidate_id=old_media.id
                )
                is None
            )
        async with client.app.state.database.session() as session:
            assert (
                await worker.process_once(
                    session, now=now + timedelta(days=8), candidate_id=old_media.id
                )
            ).status == "deleted"

    client.portal.call(retain_and_remove_old)
    with pytest.raises(S3Error):
        sdk.stat_object(old_media.bucket_name, old_media.object_key)
    assert client.delete("/api/auth/me", headers=owner).status_code == 200
    assert (
        client.get(f"/api/people/{replaced['slug']}/avatar/{replaced['avatar_id']}").status_code
        == 404
    )

    async def purge():
        worker = ProjectMediaReconciler(client.app.state.storage)
        async with client.app.state.database.session() as session:
            assert await worker.purge_deleted_data(session, limit=1, dry_run=True) == (0, 0, 1)
            assert await session.get(PublicUserProfile, replaced["id"]) is not None
        async with client.app.state.database.session() as session:
            assert await worker.purge_deleted_data(session, limit=1) == (0, 0, 1)
            current = await session.get(MediaObject, replaced["avatar_id"])
            assert (
                await worker.process_once(
                    session, now=datetime.now(timezone.utc), candidate_id=current.id
                )
            ).status == "deleted"
            return current.bucket_name, current.object_key

    bucket, key = client.portal.call(purge)
    with pytest.raises(S3Error):
        sdk.stat_object(bucket, key)


@pytest.mark.parametrize("cancel_count", [1, 3])
def test_cancelled_avatar_upload_keeps_sql_lock_until_real_put_finishes(
    profile_storage, monkeypatch, cancel_count
):
    client, _, sdk, (owner, _), users = profile_storage
    create_profile(client, owner)

    async def scenario():
        entered, release = threading.Event(), threading.Event()
        original = sdk.put_object

        def delayed(*args, **kwargs):
            entered.set()
            assert release.wait(10)
            return original(*args, **kwargs)

        monkeypatch.setattr(sdk, "put_object", delayed)

        async def perform():
            async with client.app.state.database.session() as session:
                return await AvatarService(client.app.state.storage).upload(
                    session,
                    user_id=users[0],
                    expected_version=1,
                    data=image_bytes(),
                    original_filename="avatar.png",
                )

        task = asyncio.create_task(perform())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            for _ in range(cancel_count):
                task.cancel()
                await asyncio.sleep(0.02)
                assert not task.done()
            worker = ProjectMediaReconciler(client.app.state.storage)
            async with client.app.state.database.session() as session:
                assert (
                    await asyncio.wait_for(
                        worker.process_once(
                            session, now=datetime.now(timezone.utc) + timedelta(hours=2)
                        ),
                        3,
                    )
                    is None
                )
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            async with client.app.state.database.session() as session:
                media = await session.scalar(
                    select(MediaObject).where(MediaObject.uploaded_by_user_id == users[0])
                )
                assert media.status == "pending"
                assert sdk.stat_object(media.bucket_name, media.object_key).size > 0
                assert (
                    await worker.process_once(
                        session,
                        now=datetime.now(timezone.utc) + timedelta(hours=2),
                        candidate_id=media.id,
                    )
                ).status == "deleted"
                assert (
                    await session.scalar(
                        select(PublicUserProfile).where(PublicUserProfile.user_id == users[0])
                    )
                ).avatar_media_id is None
            with pytest.raises(S3Error):
                sdk.stat_object(media.bucket_name, media.object_key)
        finally:
            release.set()
            if not task.done():
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    client.portal.call(scenario)


def test_version_is_rechecked_after_durable_pending_commit(profile_storage, monkeypatch):
    client, _, _, (owner, _), users = profile_storage
    saved = create_profile(client, owner)

    async def scenario():
        service = AvatarService(client.app.state.storage)
        original = service.profiles.lock_owned
        entered, release = asyncio.Event(), asyncio.Event()
        calls = 0

        async def gate(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                entered.set()
                await release.wait()
            return await original(*args, **kwargs)

        monkeypatch.setattr(service.profiles, "lock_owned", gate)

        async def perform():
            async with client.app.state.database.session() as session:
                return await service.upload(
                    session,
                    user_id=users[0],
                    expected_version=1,
                    data=image_bytes(),
                    original_filename="avatar.png",
                )

        task = asyncio.create_task(perform())
        try:
            await asyncio.wait_for(entered.wait(), 5)
            async with client.app.state.database.session() as session:
                await PublicProfileService().save(
                    session,
                    users[0],
                    PublicProfileWrite.model_validate(write_body(saved, display_name="Newer text")),
                )
                await session.commit()
            release.set()
            with pytest.raises(ProfileConflictError):
                await task
            async with client.app.state.database.session() as session:
                own = await PublicProfileService().own(session, users[0])
                assert (
                    own.version == 2 and own.display_name == "Newer text" and own.avatar_id is None
                )
                assert (
                    await session.scalar(
                        select(MediaObject).where(MediaObject.uploaded_by_user_id == users[0])
                    )
                ).status == "pending"
                assert (
                    await ProjectMediaReconciler(client.app.state.storage).process_once(
                        session, now=datetime.now(timezone.utc) + timedelta(hours=2)
                    )
                ).status == "deleted"
        finally:
            release.set()
            if not task.done():
                await task

    client.portal.call(scenario)


def test_two_concurrent_avatar_saves_have_one_confirmed_winner(profile_storage):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client, _, _, (owner, _), _ = profile_storage
    create_profile(client, owner)
    barrier = Barrier(2)

    def perform(index):
        barrier.wait(10)
        return upload(client, owner, data=image_bytes(size=(40 + index, 40)))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(perform, [0, 1]))
    assert sorted(response.status_code for response in responses) == [201, 409]
    winner = next(response.json() for response in responses if response.status_code == 201)
    assert client.get(OWN, headers=owner).json() == winner
    assert winner["version"] == 2
    assert client.get(f"{UPLOAD}/{winner['avatar_id']}", headers=owner).status_code == 200
