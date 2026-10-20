"""Design API and cleanup with real PostgreSQL and a private disposable MinIO bucket."""

import asyncio
import os
import threading
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.factory import create_app
from app.integrations.minio import MinioStorage
from app.modules.catalog.models import Product, ProductCategory
from app.modules.customer_projects.lifecycle import ProjectMediaReconciler
from app.modules.design_assets.models import CartDesignAsset, DesignAsset, OrderDesignAsset
from app.modules.design_assets.repository import DesignAssetRepository
from app.modules.design_assets.service import DesignMediaService
from app.modules.identity.models import User
from app.modules.media.models import MediaObject
from app.modules.orders.models import Order
from scripts.reconcile_project_media import process_batch
from tests.contract.test_design_media_api import image_bytes
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.integration.test_project_media_minio import real_storage as real_storage
from tests.postgres_schema import migrate
from tests.projects_scenario import project_payload

pytestmark = pytest.mark.skipif(
    not os.getenv("MINIO_TEST_CONFIG_PATH") or not os.getenv("SCHEMA_TEST_POSTGRES_URL"),
    reason="Requires disposable PostgreSQL and MinIO",
)


@pytest.fixture
def design_env(postgres_url, real_storage):
    config, sdk, prefix, public_base = real_storage
    migrate(postgres_url, "upgrade", "head")
    base = favorite_settings(postgres_url)
    settings = Settings(
        _env_file=None,
        **{
            **base.model_dump(),
            "carts_v2_enabled": True,
            "minio_enabled": True,
            "minio_endpoint": config["endpoint"],
            "minio_access_key": config["access_key"],
            "minio_secret_key": config["secret_key"],
            "minio_bucket_prefix": prefix,
            "minio_public_base_url": public_base,
        },
    )
    products, tokens, users = asyncio.run(seed_favorites(settings, create_schema=False))
    try:
        yield settings, sdk, products, users, tokens
    finally:

        async def cleanup():
            database = DatabaseManager(settings)
            await database.startup()
            try:
                async with database.session() as session:
                    ids = (
                        select(DesignAsset.id)
                        .join(MediaObject)
                        .where(MediaObject.bucket_name == settings.minio_customer_projects_bucket)
                    )
                    await session.execute(
                        delete(CartDesignAsset).where(CartDesignAsset.design_asset_id.in_(ids))
                    )
                    await session.execute(
                        delete(OrderDesignAsset).where(OrderDesignAsset.design_asset_id.in_(ids))
                    )
                    await session.execute(delete(DesignAsset).where(DesignAsset.id.in_(ids)))
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


def test_guest_upload_restart_dry_run_and_physical_expiry_cleanup(design_env):
    settings, sdk, _, _, _ = design_env
    with TestClient(create_app(settings=settings)) as client:
        created = client.post("/api/design-media", content=image_bytes())
        assert created.status_code == 201, created.text
        path = created.json()["url"]
        read = client.get(path)
        assert read.status_code == 200
        assert len(read.content) > 64 * 1024
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(path).content == read.content

    async def scenario():
        database = DatabaseManager(settings)
        await database.startup()
        worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
        try:
            async with database.session() as session:
                asset, media = (
                    await session.execute(select(DesignAsset, MediaObject).join(MediaObject))
                ).one()
                assert sdk.stat_object(media.bucket_name, media.object_key).size == len(
                    read.content
                )
                with pytest.raises(HTTPError) as denied:
                    urlopen(
                        f"http://{settings.minio_endpoint}/{media.bucket_name}/{media.object_key}",
                        timeout=5,
                    )
                assert denied.value.code == 403
                await session.execute(
                    update(DesignAsset)
                    .where(DesignAsset.id == asset.id)
                    .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
                )
                await session.commit()
                asset_id, media_id, key = asset.id, media.id, media.object_key
            dry = await process_batch(database, worker, max_items=10, dry_run=True)
            assert dry["design_media"] == 1
            async with database.session() as session:
                assert await session.get(DesignAsset, asset_id) is not None
            assert sdk.stat_object(settings.minio_customer_projects_bucket, key).size > 0
            counts = await process_batch(database, worker, max_items=10, dry_run=False)
            assert counts["design_media"] == 1 and counts["deleted"] == 1
            async with database.session() as session:
                assert await session.get(DesignAsset, asset_id) is None
                assert await session.get(MediaObject, media_id) is None
            assert list(sdk.list_objects(settings.minio_customer_projects_bucket, prefix=key)) == []
        finally:
            await database.shutdown()

    asyncio.run(scenario())
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(path).status_code == 404


def test_imported_file_retained_by_order_survives_project_and_account_deletion(design_env):
    settings, sdk, products, _, (owner, other) = design_env
    with TestClient(create_app(settings=settings)) as client:
        uploaded = client.post(
            "/api/profile/project-media",
            headers=owner,
            files={"file": ("image.png", image_bytes(), "image/png")},
        )
        assert uploaded.status_code == 201
        media_id = uploaded.json()["id"]
        saved = client.post(
            "/api/profile/projects", headers=owner, json=project_payload(products[0], media_id)
        )
        assert saved.status_code == 201, saved.text
        assert (
            client.post(
                "/api/design-media/import", headers=other, json={"media_ids": [media_id]}
            ).status_code
            == 404
        )
        imported = client.post(
            "/api/design-media/import", headers=owner, json={"media_ids": [media_id]}
        )
        assert imported.status_code == 201
        path = imported.json()["items"][0]["url"]

        async def retain():
            database = DatabaseManager(settings)
            await database.startup()
            try:
                async with database.session() as session:
                    order = Order(
                        items_subtotal=0,
                        delivery_price=0,
                        total_price=0,
                        request_fingerprint_sha256="e" * 64,
                    )
                    session.add(order)
                    await session.flush()
                    asset = await session.scalar(
                        select(DesignAsset)
                        .where(DesignAsset.media_object_id == media_id)
                        .with_for_update()
                    )
                    await DesignAssetRepository().retain_order(
                        session, order_id=order.id, assets=[asset]
                    )
                    await session.commit()
                    return order.id
            finally:
                await database.shutdown()

        order_id = asyncio.run(retain())
        try:
            assert (
                client.delete(
                    f"/api/profile/projects/{saved.json()['id']}",
                    headers=owner,
                    params={"expected_version": 1},
                ).status_code
                == 204
            )
            assert client.delete("/api/auth/me", headers=owner).status_code == 200

            async def clean():
                database = DatabaseManager(settings)
                await database.startup()
                try:
                    counts = await process_batch(
                        database,
                        ProjectMediaReconciler(MinioStorage(settings, client=sdk)),
                        max_items=100,
                        dry_run=False,
                    )
                    assert counts.get("deleted", 0) == 0
                    async with database.session() as session:
                        assert await session.get(Order, order_id) is not None
                        assert await session.get(MediaObject, media_id) is not None
                finally:
                    await database.shutdown()

            asyncio.run(clean())
            assert client.get(path).status_code == 200
        finally:

            async def remove_order():
                database = DatabaseManager(settings)
                await database.startup()
                try:
                    async with database.session() as session:
                        await session.execute(delete(Order).where(Order.id == order_id))
                        await session.commit()
                finally:
                    await database.shutdown()

            asyncio.run(remove_order())


def test_interruption_after_object_put_leaves_pending_intent_for_cleanup(design_env, monkeypatch):
    settings, sdk, _, _, _ = design_env

    def interrupted(*args, **kwargs):
        raise RuntimeError("simulated stop after object PUT")

    monkeypatch.setattr(DesignMediaService, "create_reference", interrupted)
    with TestClient(create_app(settings=settings), raise_server_exceptions=False) as client:
        assert client.post("/api/design-media", content=image_bytes()).status_code == 500

    async def scenario():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                media = (
                    await session.scalars(
                        select(MediaObject).where(MediaObject.object_key.startswith("designs/"))
                    )
                ).one()
                assert media.status == "pending"
                assert sdk.stat_object(media.bucket_name, media.object_key).size > 0
                assert await session.scalar(select(DesignAsset.id)) is None
            worker = ProjectMediaReconciler(MinioStorage(settings, client=sdk))
            async with database.session() as session:
                result = await worker.process_once(
                    session, now=datetime.now(timezone.utc) + timedelta(hours=2)
                )
                assert result.status == "deleted"
                assert list(sdk.list_objects(media.bucket_name, prefix=media.object_key)) == []
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cancelled_guest_upload_holds_lock_until_real_object_put_finishes(design_env, monkeypatch):
    settings, sdk, _, _, _ = design_env

    async def scenario():
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
                return await DesignMediaService(MinioStorage(settings, client=sdk)).upload(
                    session, data=image_bytes(), now=datetime.now(timezone.utc)
                )

        task = asyncio.create_task(upload())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            task.cancel()
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


@pytest.mark.parametrize("fault,expected", [("missing", 404), ("corrupt", 503)])
def test_real_missing_or_corrupt_object_is_not_served(design_env, fault, expected):
    settings, sdk, _, _, _ = design_env
    with TestClient(create_app(settings=settings)) as client:
        created = client.post("/api/design-media", content=image_bytes())
        assert created.status_code == 201
        path = created.json()["url"]

        async def stored():
            database = DatabaseManager(settings)
            await database.startup()
            try:
                async with database.session() as session:
                    return (
                        await session.scalars(
                            select(MediaObject).where(MediaObject.object_key.startswith("designs/"))
                        )
                    ).one()
            finally:
                await database.shutdown()

        media = asyncio.run(stored())
        if fault == "missing":
            sdk.remove_object(media.bucket_name, media.object_key)
        else:
            sdk.put_object(
                media.bucket_name,
                media.object_key,
                BytesIO(b"corrupt"),
                7,
                content_type="image/webp",
            )
        result = client.get(path)
        assert result.status_code == expected
        assert media.object_key not in result.text
        assert result.headers["cache-control"] == "private, no-store"
