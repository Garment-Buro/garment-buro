from __future__ import annotations

import asyncio
import re
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.media.models import MediaObject, MediaStatus
from app.modules.media.service import (
    MediaService,
    UnsupportedMediaError,
    prepare_catalog_media,
)
from tests.fakes.minio import FakeMinioClient


def make_webp() -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(output, format="WEBP")
    return output.getvalue()


def runtime_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.test",
    )


def test_prepared_webp_is_not_recompressed() -> None:
    original = make_webp()

    prepared = prepare_catalog_media(original)

    assert prepared.data == original
    assert prepared.content_type == "image/webp"
    assert prepared.extension == ".webp"


def test_media_service_persists_intent_and_ready_metadata() -> None:
    async def scenario() -> None:
        settings = runtime_settings()
        database = DatabaseManager(settings)
        client = FakeMinioClient()
        storage = MinioStorage(settings, client=client)
        service = MediaService(storage)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with database.session() as session:
            result = await service.upload_catalog_media(
                session,
                data=make_webp(),
                original_filename="../каталог.webp",
            )

        async with database.session() as session:
            media = await session.scalar(select(MediaObject))

        assert media is not None
        assert media.status == MediaStatus.READY.value
        assert media.original_filename == "каталог.webp"
        assert media.etag == "etag-1"
        assert media.checksum_sha256 == result.checksum_sha256
        assert result.media_id == media.id
        assert result.public_url.startswith("https://cdn.test/garment-buro-test-media/catalog/")
        assert re.fullmatch(
            r"catalog/\d{4}/\d{2}/\d{2}/[0-9a-f]{32}\.webp",
            result.object_key,
        )
        assert len(client.uploads) == 1
        await database.shutdown()

    asyncio.run(scenario())


def test_media_service_marks_metadata_failed_when_storage_fails() -> None:
    class FailingClient(FakeMinioClient):
        def put_object(self, *args, **kwargs):
            raise OSError("storage unavailable")

    async def scenario() -> None:
        settings = runtime_settings()
        database = DatabaseManager(settings)
        storage = MinioStorage(settings, client=FailingClient())
        service = MediaService(storage)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        with pytest.raises(OSError, match="storage unavailable"):
            async with database.session() as session:
                await service.upload_catalog_media(
                    session,
                    data=make_webp(),
                    original_filename="product.webp",
                )

        async with database.session() as session:
            media = await session.scalar(select(MediaObject))

        assert media is not None
        assert media.status == MediaStatus.FAILED.value
        await database.shutdown()

    asyncio.run(scenario())


def test_media_service_rejects_svg_and_arbitrary_bytes_before_storage() -> None:
    async def scenario() -> None:
        settings = runtime_settings()
        database = DatabaseManager(settings)
        client = FakeMinioClient()
        service = MediaService(MinioStorage(settings, client=client))
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        with pytest.raises(UnsupportedMediaError, match="Only JPEG"):
            async with database.session() as session:
                await service.upload_catalog_media(
                    session,
                    data=b"<svg><script>alert(1)</script></svg>",
                    original_filename="unsafe.svg",
                )

        assert client.uploads == []
        await database.shutdown()

    asyncio.run(scenario())
