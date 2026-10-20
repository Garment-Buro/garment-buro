from __future__ import annotations

import asyncio
from io import BytesIO

import pytest

from app.core.config import AppEnvironment, Settings
from app.integrations.minio import MinioStorage
from tests.fakes.minio import FakeMinioClient


def storage_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": AppEnvironment.TEST,
        "minio_enabled": True,
        "minio_access_key": "test-access",
        "minio_secret_key": "test-secret",
        "minio_public_base_url": "https://cdn.test/assets",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_minio_storage_upload_remove_and_presign_contract() -> None:
    async def scenario() -> None:
        client = FakeMinioClient()
        storage = MinioStorage(storage_settings(), client=client)

        assert await storage.ping()
        stored = await storage.put_object(
            object_key="catalog/2026/image name.webp",
            data=b"webp-bytes",
            content_type="image/webp",
        )

        assert stored.bucket_name == "garment-buro-test-media"
        assert stored.etag == "etag-1"
        assert stored.version_id == "version-1"
        assert stored.public_url == (
            "https://cdn.test/assets/garment-buro-test-media/catalog/2026/image%20name.webp"
        )
        assert client.uploads == [
            {
                "bucket_name": "garment-buro-test-media",
                "object_name": "catalog/2026/image name.webp",
                "data": b"webp-bytes",
                "length": 10,
                "content_type": "image/webp",
            }
        ]

        signed_url = await storage.presigned_get_url("private/crm/spec.pdf")
        assert (
            signed_url
            == "https://cdn.test/assets/garment-buro-test-media/private/crm/spec.pdf?ttl=900"
        )

        private = await storage.put_private_crm_object(
            object_key="crm/pattern/2026/08/13/pattern.pdf",
            data=b"private-pdf",
            content_type="application/pdf",
        )
        assert private.public_url is None
        private_url = await storage.presigned_crm_get_url(
            private.object_key,
            filename="pattern.pdf",
        )
        assert private_url.startswith("https://cdn.test/assets/garment-buro-test-crm-private/")
        assert private_url.endswith("?ttl=900&download=1")
        preview_url = await storage.presigned_crm_preview_url(
            private.object_key,
            filename="pattern.pdf",
            content_type="application/pdf",
        )
        assert preview_url.endswith("?ttl=900&download=1")
        assert client.presigns[-1]["response_headers"] == {
            "response-content-disposition": "inline; filename*=UTF-8''pattern.pdf",
            "response-content-type": "application/pdf",
        }
        assert await storage.private_crm_object_exists(private.object_key)
        assert await storage.get_private_crm_bucket_policy() == ""
        await storage.remove_private_crm_object(private.object_key)
        assert not await storage.private_crm_object_exists(private.object_key)

        await storage.remove_object("catalog/2026/image name.webp")
        assert client.removed == [
            (
                "garment-buro-test-crm-private",
                "crm/pattern/2026/08/13/pattern.pdf",
            ),
            ("garment-buro-test-media", "catalog/2026/image name.webp"),
        ]

    asyncio.run(scenario())


def test_minio_storage_rejects_unsafe_or_oversized_objects() -> None:
    async def scenario() -> None:
        storage = MinioStorage(
            storage_settings(media_max_upload_bytes=4),
            client=FakeMinioClient(),
        )

        with pytest.raises(ValueError, match="Invalid object key"):
            await storage.put_object(
                object_key="../secret.txt",
                data=b"data",
                content_type="text/plain",
            )

        with pytest.raises(ValueError, match="must not be empty"):
            await storage.put_object(
                object_key="safe/empty.txt",
                data=b"",
                content_type="text/plain",
            )

        with pytest.raises(ValueError, match="exceeds"):
            await storage.put_object(
                object_key="safe/large.txt",
                data=b"12345",
                content_type="text/plain",
            )

    asyncio.run(scenario())


def test_minio_storage_reports_missing_bucket_as_not_ready() -> None:
    storage = MinioStorage(
        storage_settings(),
        client=FakeMinioClient(bucket_available=False),
    )

    assert not asyncio.run(storage.ping())


def test_private_projects_bucket_must_exist_and_have_no_bucket_policy() -> None:
    class MissingProjects(FakeMinioClient):
        def bucket_exists(self, bucket_name):
            return bucket_name != "garment-buro-test-projects"

    assert not asyncio.run(MinioStorage(storage_settings(), client=MissingProjects()).ping())
    private = FakeMinioClient()
    assert asyncio.run(MinioStorage(storage_settings(), client=private).ping())
    public = FakeMinioClient(
        projects_bucket_policy='{"Statement":[{"Effect":"Allow","Principal":"*"}]}'
    )
    assert not asyncio.run(MinioStorage(storage_settings(), client=public).ping())


@pytest.mark.parametrize("failure", [None, "oversized", "read", "close"])
def test_private_binary_read_is_bounded_and_always_releases_response(failure):
    """Removing either finally or its nested cleanup leaks SDK connections."""

    class Body(BytesIO):
        released = False
        requested = None

        def read(self, size=-1):
            self.requested = size
            if failure == "read":
                raise OSError("Interrupted storage response")
            return super().read(size)

        def close(self):
            super().close()
            if failure == "close":
                raise OSError("Failed storage close")

        def release_conn(self):
            self.released = True

    body = Body(b"12345" if failure == "oversized" else b"1234")

    class Client(FakeMinioClient):
        def get_object(self, bucket_name, object_name, *, version_id=None):
            assert bucket_name == "garment-buro-test-projects"
            assert object_name == "profiles/1/avatar.webp" and version_id == "stored-version"
            return body

    storage = MinioStorage(storage_settings(), client=Client())
    operation = storage.read_private_customer_object(
        "profiles/1/avatar.webp", max_bytes=4, version_id="stored-version"
    )
    if failure is None:
        assert asyncio.run(operation) == b"1234"
    else:
        with pytest.raises(OSError):
            asyncio.run(operation)
    assert body.requested == 5 and body.closed and body.released
