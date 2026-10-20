"""HTTP contract with SQLite and synthetic storage; real storage checks are separate."""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO
from random import Random

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, update

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.factory import create_app
from app.integrations.minio import MinioStorage
from app.modules.design_assets.models import DesignAsset
from app.modules.design_assets.security import (
    digest_design_asset_token,
    token_from_design_asset_path,
)
from app.modules.media.models import MediaObject
from tests.contract.test_public_profile_media import AvatarClient
from tests.favorites_scenario import favorite_settings, seed_favorites

UPLOAD = "/api/design-media"


@pytest.fixture
def setup(tmp_path):
    base = favorite_settings(f"sqlite+aiosqlite:///{tmp_path / 'design.db'}")
    settings = Settings(
        _env_file=None,
        **{
            **base.model_dump(),
            "carts_v2_enabled": True,
            "minio_enabled": True,
            "minio_access_key": "test-access",
            "minio_secret_key": "test-secret",
            "minio_public_base_url": "https://cdn.test/assets",
        },
    )
    products, tokens, users = asyncio.run(seed_favorites(settings))
    return settings, products, tokens, users


def image_bytes():
    pixels = bytearray(Random(7).randbytes(192 * 192 * 4))
    pixels[3::4] = b"\x80" * (192 * 192)
    image = Image.frombytes("RGBA", (192, 192), bytes(pixels))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


async def inspect(settings, *, expire=False):
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            if expire:
                await session.execute(
                    update(DesignAsset).values(
                        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
                    )
                )
                await session.commit()
            return list(await session.scalars(select(DesignAsset))), list(
                await session.scalars(select(MediaObject))
            )
    finally:
        await database.shutdown()


def test_guest_upload_returns_stable_private_content_after_application_restart(setup, caplog):
    settings, _, _, _ = setup
    sdk = AvatarClient()
    caplog.set_level(logging.INFO, logger="app.http")
    original = image_bytes()
    assert len(original) > 64 * 1024
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        created = client.post(UPLOAD, content=original, headers={"Content-Type": "text/plain"})
        assert created.status_code == 201, created.text
        result = created.json()
        assert result["size_bytes"] > 64 * 1024
        assert result["content_type"] == "image/webp"
        path = result["url"]
        token = token_from_design_asset_path(path)
        assert token
        read = client.get(path)
        assert read.status_code == 200, read.text
        assert read.headers["content-type"] == "image/webp"
        assert read.headers["cache-control"] == "private, no-store"
        assert read.headers["x-content-type-options"] == "nosniff"
        assert read.headers["referrer-policy"] == "no-referrer"
        with Image.open(BytesIO(read.content)) as decoded, Image.open(BytesIO(original)) as source:
            assert decoded.tobytes() == source.tobytes()
        assert client.get(path.replace(token, "x" * 43)).status_code == 404
        assert client.get(UPLOAD + "/invalid/content").status_code == 404
    with TestClient(create_app(settings=settings)) as restarted:
        restarted.app.state.storage = MinioStorage(settings, client=sdk)
        assert restarted.get(path).content == read.content
    (asset,), (media,) = asyncio.run(inspect(settings))
    assert asset.access_digest_sha256 == digest_design_asset_token(token)
    assert token not in str(vars(asset))
    assert asset.media_object_id == media.id
    assert media.uploaded_by_user_id is None
    assert media.object_key.startswith("designs/")
    assert not media.is_public and media.status == "ready"
    assert hashlib.sha256(read.content).hexdigest() == media.checksum_sha256
    access_events = [record for record in caplog.records if record.name == "app.http"]
    assert access_events
    assert all(token not in str(vars(record)) for record in access_events)


@pytest.mark.parametrize("data", [b"", b"not image", b"<svg></svg>", image_bytes()[:25]])
def test_invalid_rasters_create_no_rows_or_storage_objects(setup, data):
    settings, _, _, _ = setup
    sdk = AvatarClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        assert client.post(UPLOAD, content=data).status_code == 415
    assert asyncio.run(inspect(settings)) == ([], [])
    assert sdk.uploads == []


def test_chunked_upload_stops_at_byte_limit_before_creating_pending_metadata(setup):
    settings, _, _, _ = setup
    sdk = AvatarClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        result = client.post(UPLOAD, content=(b"x" * 1024 * 1024 for _ in range(9)))
        assert result.status_code == 413
    assert asyncio.run(inspect(settings)) == ([], [])
    assert sdk.uploads == []


@pytest.mark.parametrize("proxy_error", [False, True])
def test_failed_put_leaves_durable_failed_metadata_without_capability(setup, proxy_error):
    class Offline(AvatarClient):
        def put_object(self, *args, **kwargs):
            if proxy_error:
                from minio.error import InvalidResponseError

                raise InvalidResponseError(503, "text/html", "private SDK internals")
            raise OSError("private SDK internals")

    settings, _, _, _ = setup
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=Offline())
        result = client.post(UPLOAD, content=image_bytes())
        assert result.status_code == 503
        assert "internals" not in result.text
        assert "url" not in result.json()
    assets, (media,) = asyncio.run(inspect(settings))
    assert assets == []
    assert media.status == "failed"


def test_owned_project_media_import_requires_identity_and_never_reuses_presigned_url(setup):
    settings, _, (owner, other), _ = setup
    sdk = AvatarClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        uploaded = client.post(
            "/api/profile/project-media",
            headers=owner,
            files={"file": ("private.png", image_bytes(), "image/png")},
        )
        assert uploaded.status_code == 201
        media_id = uploaded.json()["id"]
        payload = {"media_ids": [media_id, media_id]}
        assert client.post(UPLOAD + "/import", json=payload).status_code == 401
        assert client.post(UPLOAD + "/import", json=payload, headers=other).status_code == 404
        assert (
            client.post(
                UPLOAD + "/import", json={"media_ids": [media_id, 999999]}, headers=owner
            ).status_code
            == 404
        )
        assert asyncio.run(inspect(settings))[0] == []
        result = client.post(UPLOAD + "/import", json=payload, headers=owner)
        assert result.status_code == 201, result.text
        (item,) = result.json()["items"]
        assert item["media_id"] == media_id
        assert client.get(item["url"]).status_code == 200
        assert sdk.presigns == []
        for invalid in [[], [0], [True], [2**32], [media_id] * 103]:
            assert (
                client.post(
                    UPLOAD + "/import", headers=owner, json={"media_ids": invalid}
                ).status_code
                == 422
            )
    assert len(asyncio.run(inspect(settings))[0]) == 1


def test_expired_capability_and_corrupted_object_are_not_served(setup):
    settings, _, _, _ = setup
    sdk = AvatarClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        path = client.post(UPLOAD, content=image_bytes()).json()["url"]
        sdk.uploads[0]["data"] = b"corrupt"
        assert client.get(path).status_code == 503
        asyncio.run(inspect(settings, expire=True))
        assert client.get(path).status_code == 404


def test_public_bucket_policy_and_disabled_storage_close_the_design_api(setup):
    settings, _, _, _ = setup
    sdk = AvatarClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        path = client.post(UPLOAD, content=image_bytes()).json()["url"]
        sdk.projects_bucket_policy = '{"Statement":[{"Effect":"Allow","Principal":"*"}]}'
        assert client.get(path).status_code == 503
        assert client.post(UPLOAD, content=image_bytes()).status_code == 503
    with TestClient(
        create_app(settings=settings.model_copy(update={"minio_enabled": False}))
    ) as client:
        assert client.post(UPLOAD, content=image_bytes()).status_code == 503
    assert len(asyncio.run(inspect(settings))[0]) == 1


def test_guest_designs_work_when_identity_feature_is_disabled(setup):
    settings, _, _, _ = setup
    settings = settings.model_copy(update={"identity_api_enabled": False})
    sdk = AvatarClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        created = client.post(UPLOAD, content=image_bytes())
        assert created.status_code == 201
        assert client.get(created.json()["url"]).status_code == 200
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            assert (
                client.post(
                    UPLOAD + "/import", json={"media_ids": [1]}, headers=headers
                ).status_code
                == 404
            )
