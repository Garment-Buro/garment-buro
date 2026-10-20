"""HTTP/storage-boundary checks; real PostgreSQL/MinIO coverage lives in integration."""

import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, update

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.factory import create_app
from app.integrations.minio import MinioStorage
from app.modules.identity.models import User
from app.modules.media.models import MediaObject
from tests.contract.test_public_profiles import profile
from tests.fakes.minio import FakeMinioClient
from tests.favorites_scenario import favorite_settings, seed_favorites

OWN = "/api/profile/public"
UPLOAD = OWN + "/avatar"


class ObjectBody(BytesIO):
    def release_conn(self):
        pass


class AvatarClient(FakeMinioClient):
    def get_object(self, bucket_name, object_name, version_id=None):
        for upload in reversed(self.uploads):
            if upload["bucket_name"] == bucket_name and upload["object_name"] == object_name:
                return ObjectBody(upload["data"])
        raise OSError("Object unavailable")


@pytest.fixture
def media_setup(tmp_path):
    base = favorite_settings(f"sqlite+aiosqlite:///{tmp_path / 'avatar.db'}")
    settings = Settings(
        _env_file=None,
        **{
            **base.model_dump(),
            "minio_enabled": True,
            "minio_access_key": "test-access",
            "minio_secret_key": "test-secret",
            "minio_public_base_url": "https://cdn.test/assets",
        },
    )
    _, tokens, users = asyncio.run(seed_favorites(settings))
    sdk = AvatarClient()
    with TestClient(create_app(settings=settings)) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        yield client, sdk, tokens, users


def image_bytes(size=(1200, 600), format="PNG", exif=None):
    stream = BytesIO()
    image = Image.new("RGBA" if format != "JPEG" else "RGB", size, (20, 40, 60))
    image.save(stream, format=format, **({"exif": exif} if exif is not None else {}))
    return stream.getvalue()


def create_profile(client, token, **changes):
    response = client.put(OWN, headers=token, json=profile(**changes))
    assert response.status_code == 200, response.text
    return response.json()


def write_body(saved, **changes):
    return {
        **{key: saved[key] for key in ("slug", "display_name", "bio", "is_published", "version")},
        **changes,
    }


def upload(client, token, version=1, data=None):
    return client.post(
        UPLOAD,
        headers=token,
        params={"expected_version": version},
        files={"file": ("../private.png", image_bytes() if data is None else data, "text/plain")},
    )


async def media_rows(settings):
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            return list(await session.scalars(select(MediaObject).order_by(MediaObject.id)))
    finally:
        await database.shutdown()


def test_avatar_is_private_normalized_owned_and_persisted(media_setup):
    client, sdk, (owner, other), users = media_setup
    original = create_profile(client, owner)
    response = upload(client, owner)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["version"] == 2 and saved["avatar_id"] > 0
    assert saved["is_published"] is False and saved["slug"] == original["slug"]
    assert response.headers["cache-control"] == "no-store"
    endpoint = f"{UPLOAD}/{saved['avatar_id']}"
    own = client.get(endpoint, headers=owner)
    assert own.status_code == 200
    assert own.headers["content-type"] == "image/webp"
    assert own.headers["cache-control"] == "no-store"
    assert own.headers["x-content-type-options"] == "nosniff"
    with Image.open(BytesIO(own.content)) as decoded:
        assert decoded.size == (512, 256)
        assert decoded.format == "WEBP"
        assert decoded.getpixel((0, 0))[:3] == (20, 40, 60)
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers=other).status_code == 404
    assert client.get(f"/api/people/{saved['slug']}/avatar/{saved['avatar_id']}").status_code == 404
    assert (
        client.get(
            f"/api/profile/project-media/{saved['avatar_id']}/access", headers=owner
        ).status_code
        == 404
    )
    (stored,) = asyncio.run(media_rows(client.app.state.settings))
    assert stored.uploaded_by_user_id == users[0] and not stored.is_public
    assert stored.status == "ready" and stored.content_type == "image/webp"
    assert stored.object_key.startswith(f"profiles/{users[0]}/")
    assert stored.bucket_name.endswith("-projects")
    assert stored.original_filename == "private.png"
    assert own.content == sdk.uploads[0]["data"]
    with TestClient(create_app(settings=client.app.state.settings)) as restarted:
        restarted.app.state.storage = MinioStorage(client.app.state.settings, client=sdk)
        assert restarted.get(OWN, headers=owner).json() == saved
        assert restarted.get(endpoint, headers=owner).content == own.content


@pytest.mark.parametrize("rendition", ["", "/preview"], ids=["full", "card"])
def test_public_avatar_is_revoked_on_unpublish_replace_and_remove(media_setup, rendition):
    client, _, (owner, _), _ = media_setup
    create_profile(client, owner, is_published=True)
    saved = upload(client, owner).json()
    endpoint = f"/api/people/{saved['slug']}/avatar/{saved['avatar_id']}{rendition}"
    public = client.get(endpoint)
    assert public.status_code == 200 and public.headers["cache-control"] == "no-store"
    assert "Location" not in public.headers
    assert client.get(f"/api/people/{saved['slug']}").json()["avatar_id"] == saved["avatar_id"]
    assert client.get("/api/people").json()["items"][0]["avatar_id"] == saved["avatar_id"]
    hidden = client.put(OWN, headers=owner, json=write_body(saved, is_published=False)).json()
    denied = client.get(endpoint)
    assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"
    assert client.get(f"{UPLOAD}/{saved['avatar_id']}", headers=owner).status_code == 200
    published = client.put(OWN, headers=owner, json=write_body(hidden, is_published=True)).json()
    assert client.get(endpoint).status_code == 200
    replacement = upload(client, owner, published["version"], image_bytes(size=(50, 50))).json()
    assert replacement["avatar_id"] != saved["avatar_id"]
    assert client.get(endpoint).status_code == 404
    assert client.get(f"{UPLOAD}/{saved['avatar_id']}", headers=owner).status_code == 404
    current = f"/api/people/{saved['slug']}/avatar/{replacement['avatar_id']}{rendition}"
    assert client.get(current).status_code == 200
    removed = client.delete(
        UPLOAD, headers=owner, params={"expected_version": replacement["version"]}
    )
    assert removed.status_code == 200 and removed.json()["avatar_id"] is None
    assert removed.json()["version"] == replacement["version"] + 1
    assert client.get(current).status_code == 404
    assert client.get(f"/api/people/{saved['slug']}").json()["avatar_id"] is None


@pytest.mark.parametrize("status", ["blocked", "deleted"])
def test_unavailable_account_revokes_avatar_without_storage_url(media_setup, status):
    client, _, (owner, _), users = media_setup
    create_profile(client, owner, is_published=True)
    saved = upload(client, owner).json()

    async def change_status():
        async with client.app.state.database.session() as session:
            await session.execute(update(User).where(User.id == users[0]).values(status=status))
            await session.commit()

    client.portal.call(change_status)
    assert client.get(f"/api/people/{saved['slug']}/avatar/{saved['avatar_id']}").status_code == 404
    assert (
        client.get(f"/api/people/{saved['slug']}/avatar/{saved['avatar_id']}/preview").status_code
        == 404
    )
    assert client.get(f"{UPLOAD}/{saved['avatar_id']}", headers=owner).status_code == 401


def test_card_preview_preserves_source_alpha_and_profile_without_new_storage(media_setup):
    client, sdk, (owner, _), _ = media_setup
    create_profile(client, owner, is_published=True)
    source = Image.effect_noise((1200, 600), 80).convert("RGBA")
    source.putalpha(Image.linear_gradient("L").resize(source.size))
    original = BytesIO()
    source.save(original, format="PNG")
    saved = upload(client, owner, data=original.getvalue()).json()
    endpoint = f"/api/people/{saved['slug']}/avatar/{saved['avatar_id']}"
    full = client.get(endpoint)
    stored = sdk.uploads[0]["data"]
    before = asyncio.run(media_rows(client.app.state.settings))
    card = client.get(endpoint + "/preview")
    assert card.status_code == 200 and card.headers["cache-control"] == "no-store"
    assert card.headers["x-content-type-options"] == "nosniff"
    assert card.headers["content-type"] == "image/webp" and "Location" not in card.headers
    assert len(card.content) < len(full.content) / 2
    with Image.open(BytesIO(full.content)) as decoded, Image.open(BytesIO(card.content)) as preview:
        assert decoded.size == (512, 256) and preview.size == (320, 160)
        expected_alpha = decoded.getchannel("A").resize(preview.size, Image.Resampling.LANCZOS)
        assert preview.getchannel("A").tobytes() == expected_alpha.tobytes()
        assert "exif" not in preview.info and "icc_profile" not in preview.info
    assert full.content == stored == sdk.uploads[0]["data"]
    assert client.get(endpoint).content == full.content
    assert client.get(OWN, headers=owner).json() == saved
    after = asyncio.run(media_rows(client.app.state.settings))
    assert [(row.id, row.checksum_sha256, row.size_bytes) for row in after] == [
        (row.id, row.checksum_sha256, row.size_bytes) for row in before
    ]
    assert len(sdk.uploads) == 1


def test_preview_does_not_upscale_small_photos_and_rejects_corrupted_storage(media_setup):
    client, sdk, (owner, _), _ = media_setup
    create_profile(client, owner, is_published=True)
    saved = upload(client, owner, data=image_bytes((50, 30))).json()
    endpoint = f"/api/people/{saved['slug']}/avatar/{saved['avatar_id']}/preview"
    result = client.get(endpoint)
    assert result.status_code == 200
    with Image.open(BytesIO(result.content)) as image:
        assert image.size == (50, 30)
    sdk.uploads[0]["data"] = b"x" * len(sdk.uploads[0]["data"])
    assert client.get(endpoint).status_code == 503


@pytest.mark.parametrize("data", [b"", b"<svg/>", b"bad", image_bytes()[:25], b"0000ftypvideo"])
def test_invalid_avatar_never_creates_media_or_changes_profile(media_setup, data):
    client, _, (owner, _), _ = media_setup
    original = create_profile(client, owner)
    assert upload(client, owner, data=data).status_code == 415
    assert client.get(OWN, headers=owner).json() == original
    assert asyncio.run(media_rows(client.app.state.settings)) == []


def test_avatar_requires_profile_current_version_and_private_storage(media_setup):
    client, sdk, (owner, other), _ = media_setup
    assert upload(client, owner).status_code == 404
    original = create_profile(client, owner)
    assert upload(client, {}, data=image_bytes()).status_code == 401
    assert upload(client, other).status_code == 404
    assert upload(client, owner, version=2).status_code == 409
    sdk.projects_bucket_policy = '{"Statement":[{"Effect":"Allow","Principal":"*"}]}'
    assert upload(client, owner).status_code == 503
    assert client.get(OWN, headers=owner).json() == original
    assert asyncio.run(media_rows(client.app.state.settings)) == []


def test_avatar_limits_and_metadata_are_enforced(media_setup):
    client, _, (owner, _), _ = media_setup
    create_profile(client, owner)
    assert upload(client, owner, data=b"x" * (8 * 1024 * 1024 + 1)).status_code == 413
    assert upload(client, owner, data=image_bytes((8193, 1))).status_code == 415
    assert upload(client, owner, data=image_bytes((4097, 4096))).status_code == 415
    frames = BytesIO()
    Image.new("RGB", (10, 10), "red").save(
        frames,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (10, 10), "blue")],
        duration=100,
    )
    assert upload(client, owner, data=frames.getvalue()).status_code == 415
    exif = Image.Exif()
    exif[274], exif[315] = 6, "private author"
    saved = upload(client, owner, data=image_bytes((12, 8), "JPEG", exif)).json()
    result = client.get(f"{UPLOAD}/{saved['avatar_id']}", headers=owner)
    with Image.open(BytesIO(result.content)) as decoded:
        assert decoded.size == (8, 12)
        assert "exif" not in decoded.info
    assert b"private author" not in result.content


@pytest.mark.parametrize("proxy_error", [False, True])
def test_storage_failure_is_durable_and_does_not_replace_avatar(media_setup, proxy_error):
    client, sdk, (owner, _), _ = media_setup
    create_profile(client, owner)
    saved = upload(client, owner).json()

    class OfflineClient(AvatarClient):
        def put_object(self, *args, **kwargs):
            if proxy_error:
                from minio.error import InvalidResponseError

                raise InvalidResponseError(503, "text/html", "internal private storage details")
            raise OSError("internal private storage details")

    client.app.state.storage = MinioStorage(client.app.state.settings, client=OfflineClient())
    failed = upload(client, owner, version=2)
    assert failed.status_code == 503 and "internal" not in failed.text
    assert client.get(OWN, headers=owner).json() == saved
    records = asyncio.run(media_rows(client.app.state.settings))
    assert [row.status for row in records] == ["ready", "failed"]
    client.app.state.storage = MinioStorage(client.app.state.settings, client=sdk)
    assert client.get(f"{UPLOAD}/{saved['avatar_id']}", headers=owner).status_code == 200


def test_removing_avatar_does_not_require_enabled_storage(media_setup):
    client, _, (owner, _), _ = media_setup
    create_profile(client, owner)
    saved = upload(client, owner).json()
    client.app.state.storage.enabled = False
    result = client.delete(UPLOAD, headers=owner, params={"expected_version": saved["version"]})
    assert result.status_code == 200
    assert result.json()["avatar_id"] is None


@pytest.mark.parametrize("operation", ["replace", "remove"])
def test_detaching_avatar_starts_a_full_cleanup_grace_period(media_setup, operation):
    client, _, (owner, _), _ = media_setup
    create_profile(client, owner)
    saved = upload(client, owner).json()
    before = datetime.now(timezone.utc)

    async def age():
        async with client.app.state.database.session() as session:
            await session.execute(
                update(MediaObject)
                .where(MediaObject.id == saved["avatar_id"])
                .values(updated_at=before - timedelta(days=100))
            )
            await session.commit()

    client.portal.call(age)
    result = (
        upload(client, owner, version=2)
        if operation == "replace"
        else client.delete(UPLOAD, headers=owner, params={"expected_version": 2})
    )
    assert result.status_code in (200, 201)
    first = asyncio.run(media_rows(client.app.state.settings))[0]
    assert first.updated_at.replace(tzinfo=timezone.utc) >= before - timedelta(seconds=1)
