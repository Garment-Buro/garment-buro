from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import event, select

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.factory import create_app
from app.integrations.minio import MinioStorage
from app.modules.media.models import MediaObject
from tests.fakes.minio import FakeMinioClient
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.projects_scenario import project_payload, seed_project_media

UPLOAD = "/api/profile/project-media"


def image_bytes(format="PNG", size=(12, 8)):
    output = BytesIO()
    Image.new("RGBA", size, (20, 40, 60, 128)).save(output, format=format)
    return output.getvalue()


@pytest.fixture
def setup(tmp_path):
    settings = favorite_settings(f"sqlite+aiosqlite:///{tmp_path / 'media.db'}")
    settings = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "minio_enabled": True,
            "minio_access_key": "test-access",
            "minio_secret_key": "test-secret",
            "minio_public_base_url": "https://cdn.test/assets",
        },
    )
    products, tokens, users = asyncio.run(seed_favorites(settings))
    return settings, products, tokens, users


async def records(settings):
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            return list(await session.scalars(select(MediaObject).order_by(MediaObject.id)))
    finally:
        await database.shutdown()


def upload(client, owner, data=None, filename="../private.png", mime="image/png"):
    return client.post(
        UPLOAD,
        headers=owner,
        files={
            "file": (filename, image_bytes() if data is None else data, mime),
        },
    )


def test_private_image_is_durable_owned_and_can_be_used_by_project(setup):
    settings, products, (owner, other), users = setup
    sdk = FakeMinioClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        created = upload(client, owner, mime="text/plain")
        assert created.status_code == 201, created.text
        assert created.headers["cache-control"] == "no-store"
        media = created.json()
        assert media["content_type"] == "image/webp"
        assert media["size_bytes"] > 0
        assert "url" not in media
        saved = client.post(
            "/api/profile/projects", headers=owner, json=project_payload(products[0], media["id"])
        )
        assert saved.status_code == 201, saved.text
        assert (
            client.post(
                "/api/profile/projects",
                headers=other,
                json=project_payload(products[0], media["id"]),
            ).status_code
            == 422
        )
        endpoint = f"{UPLOAD}/{media['id']}/access"
        for denied, expected in (
            (client.get(endpoint), 401),
            (client.get(endpoint, headers=other), 404),
        ):
            assert denied.status_code == expected
            assert "url" not in denied.json()
        access = client.get(endpoint, headers=owner)
        assert access.status_code == 200, access.text
        assert access.headers["cache-control"] == "no-store"
        assert access.json()["expires_in"] == 900
        assert access.json()["url"].startswith(
            "https://cdn.test/assets/garment-buro-test-projects/"
        )
    with TestClient(create_app(settings=settings)) as restarted:
        restarted.app.state.storage = MinioStorage(settings, client=sdk)
        assert restarted.get(endpoint, headers=owner).status_code == 200
    (stored,) = asyncio.run(records(settings))
    assert stored.uploaded_by_user_id == users[0]
    assert not stored.is_public
    assert stored.status == "ready"
    assert stored.bucket_name == "garment-buro-test-projects"
    assert stored.object_key.startswith(f"projects/{users[0]}/")
    assert stored.original_filename == "private.png"
    (uploaded,) = sdk.uploads
    assert uploaded["bucket_name"] == "garment-buro-test-projects"
    with Image.open(BytesIO(uploaded["data"])) as decoded:
        assert decoded.size == (12, 8)
        assert decoded.getpixel((0, 0)) == (20, 40, 60, 128)
        assert "exif" not in decoded.info


def test_invalid_images_never_create_metadata_or_write_storage(setup):
    settings, _, (owner, _), _ = setup
    sdk = FakeMinioClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        for data in (
            b"",
            b"<svg><script>bad()</script></svg>",
            b"not an image",
            image_bytes()[:25],
            b"0000ftypvideo",
        ):
            result = upload(client, owner, data)
            assert result.status_code == 415, result.text
        too_large = upload(client, owner, b"x" * (8 * 1024 * 1024 + 1))
        assert too_large.status_code == 413
        too_wide = upload(client, owner, image_bytes(size=(8193, 1)))
        assert too_wide.status_code == 415
        assert upload(client, {}, image_bytes()).status_code == 401
    assert asyncio.run(records(settings)) == []
    assert sdk.uploads == []


def test_malformed_exif_is_rejected_without_partial_upload(setup):
    settings, _, (owner, _), _ = setup
    sdk = FakeMinioClient()
    source = BytesIO()
    Image.new("RGB", (12, 8)).save(source, format="PNG", exif=b"bad")
    with TestClient(create_app(settings=settings), raise_server_exceptions=False) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        result = upload(client, owner, source.getvalue())
        assert result.status_code == 415
    assert asyncio.run(records(settings)) == []
    assert sdk.uploads == []


@pytest.mark.parametrize("proxy_error", [False, True])
def test_storage_failure_is_not_reported_as_saved_and_failed_media_is_inaccessible(
    setup, proxy_error
):
    class OfflineStorage(FakeMinioClient):
        def put_object(self, *args, **kwargs):
            if proxy_error:
                from minio.error import InvalidResponseError

                raise InvalidResponseError(503, "text/html", "private storage internal details")
            raise OSError("private storage internal details")

    settings, products, (owner, _), _ = setup
    with TestClient(create_app(settings=settings), raise_server_exceptions=False) as client:
        client.app.state.storage = MinioStorage(settings, client=OfflineStorage())
        failure = upload(client, owner)
        assert failure.status_code == 503, failure.text
        assert "internal details" not in failure.text
        assert failure.headers["cache-control"] == "no-store"
        (failed,) = asyncio.run(records(settings))
        assert failed.status == "failed"
        assert client.get(f"{UPLOAD}/{failed.id}/access", headers=owner).status_code == 404
        assert (
            client.post(
                "/api/profile/projects", headers=owner, json=project_payload(products[0], failed.id)
            ).status_code
            == 422
        )


def test_disabled_storage_cannot_accept_private_upload(setup):
    settings, _, (owner, _), _ = setup
    settings = settings.model_copy(update={"minio_enabled": False})
    with TestClient(create_app(settings=settings)) as client:
        assert upload(client, owner).status_code == 503
    assert asyncio.run(records(settings)) == []


def test_public_bucket_policy_blocks_upload_access_and_readiness(setup):
    settings, _, (owner, _), _ = setup
    sdk = FakeMinioClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        created = upload(client, owner)
        assert created.status_code == 201
        sdk.projects_bucket_policy = '{"Statement":[{"Effect":"Allow","Principal":"*"}]}'
        assert upload(client, owner).status_code == 503
        assert (
            client.get(f"{UPLOAD}/{created.json()['id']}/access", headers=owner).status_code == 503
        )
        assert client.get("/health/ready").status_code == 503
    assert len(asyncio.run(records(settings))) == 1
    assert len(sdk.uploads) == 1


def test_public_product_crm_and_other_account_images_cannot_be_accessed_as_private_project_media(
    setup,
):
    settings, products, (owner, _), users = setup
    media = asyncio.run(seed_project_media(settings, products, users))
    sdk = FakeMinioClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        for media_id in (media[0], media[1], media[3], media[4], 999999):
            result = client.get(f"{UPLOAD}/{media_id}/access", headers=owner)
            assert result.status_code == 404, result.text
            assert result.headers["cache-control"] == "no-store"
    assert sdk.presigns == []


def test_project_resolves_only_its_retained_images_in_one_batch(setup):
    settings, products, (owner, other), users = setup
    media = asyncio.run(seed_project_media(settings, products, users))
    sdk = FakeMinioClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        payload = project_payload(products[0], media[0])
        payload["snapshot"]["customization"]["modelImages"]["back"] = {"mediaId": media[2]}
        project = client.post("/api/profile/projects", headers=owner, json=payload).json()
        endpoint = f"/api/profile/projects/{project['id']}/media?version=1"
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if "customer_project" in statement:
                statements.append(statement)

        engine = client.app.state.database.engine.sync_engine
        event.listen(engine, "before_cursor_execute", capture)
        resolved = client.get(endpoint, headers=owner)
        event.remove(engine, "before_cursor_execute", capture)
        assert len(statements) == 1
        assert "snapshot" not in statements[0]
        assert resolved.status_code == 200, resolved.text
        assert resolved.headers["cache-control"] == "no-store"
        items = {item["id"]: item for item in resolved.json()["items"]}
        assert set(items) == {media[0], media[2]}
        assert items[media[0]]["expires_in"] is None
        assert items[media[0]]["url"].startswith("https://cdn.test/assets/garment-buro-test-media/")
        assert items[media[2]]["expires_in"] == 900
        assert len(sdk.presigns) == 1
        assert client.get(endpoint, headers=other).status_code == 404
        assert client.get(endpoint).status_code == 401
        assert (
            client.get("/api/profile/projects/999999/media?version=1", headers=owner).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/profile/projects/{project['id']}/media?version=2", headers=owner
            ).status_code
            == 409
        )
        assert (
            client.delete(
                f"/api/profile/projects/{project['id']}",
                headers=owner,
                params={"expected_version": 1},
            ).status_code
            == 204
        )
        assert client.get(endpoint, headers=owner).status_code == 404
