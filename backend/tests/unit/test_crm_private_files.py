from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.crm.file_models import CrmFileAccessEvent, CrmFileAttachment, CrmFileRole
from app.modules.crm.file_router import router as crm_file_router
from app.modules.crm.file_service import (
    CrmFileService,
    CrmFileStorageError,
    UnsupportedCrmFileError,
)
from app.modules.crm.reference_models import CrmTechCardRevision
from app.modules.identity.exceptions import PermissionDeniedError
from app.modules.identity.models import PermissionCode, User
from app.modules.identity.security import ensure_utc
from app.modules.media.models import MediaObject
from tests.fakes.minio import FakeMinioClient

NOW = datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc)


def _webp(color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 8), color=color).save(output, format="WEBP")
    return output.getvalue()


def _settings(path: Path, *, crm_file_max_upload_bytes: int = 26_214_400) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.test",
        crm_file_max_upload_bytes=crm_file_max_upload_bytes,
    )


async def _seed_revision(database: DatabaseManager) -> User:
    async with database.session() as session:
        actor = User(
            id=1,
            email="crm-files@example.test",
            email_normalized="crm-files@example.test",
            status="active",
            email_verified_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(actor)
        session.add(
            CrmTechCardRevision(
                id=1,
                tech_card_id=1,
                revision_number=1,
                status="published",
                name_snapshot="Private tech card",
                created_at=NOW,
                published_by_user_id=1,
                published_at=NOW,
            )
        )
        await session.commit()
        return actor


class StaffIdentityGate:
    def __init__(self, user: User) -> None:
        self.user = user
        self.allowed = False
        self.permissions: list[PermissionCode] = []

    async def resolve_access_token(self, *args, **kwargs) -> User:
        return self.user

    async def require_permission(
        self,
        _session,
        *,
        user_id: int,
        permission: PermissionCode,
    ) -> None:
        assert user_id == self.user.id
        self.permissions.append(permission)
        if not self.allowed:
            raise PermissionDeniedError("CRM file access denied")


class FailingMinioClient(FakeMinioClient):
    def put_object(self, *args, **kwargs):
        raise OSError("private storage unavailable")


def test_crm_file_uses_private_bucket_and_only_signed_download(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "crm-private.db")
        database = DatabaseManager(settings)
        client = FakeMinioClient()
        storage = MinioStorage(settings, client=client)
        service = CrmFileService(storage)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await _seed_revision(database)
            async with database.session() as session:
                result = await service.upload(
                    session,
                    data=_webp(),
                    original_filename="../private-pattern.webp",
                    role=CrmFileRole.PATTERN,
                    tech_card_revision_id=1,
                    actor_user_id=1,
                    now=NOW,
                )
            assert result.attachment_id == 1
            assert result.media_id == 1
            assert len(result.checksum_sha256) == 64
            assert client.uploads[0]["bucket_name"] == "garment-buro-test-crm-private"
            assert str(client.uploads[0]["object_name"]).startswith("crm/pattern/2026/08/13/")

            async with database.session() as session:
                media = await session.get(MediaObject, 1)
                attachment = await session.get(CrmFileAttachment, 1)
                download = await service.get_download(
                    session,
                    attachment_id=1,
                    actor_user_id=1,
                    now=NOW,
                )
                access_event = await session.scalar(select(CrmFileAccessEvent))
                assert media is not None and attachment is not None
                assert media.bucket_name == settings.minio_crm_bucket
                assert not media.is_public
                assert media.status == "ready"
                assert media.original_filename == "private-pattern.webp"
                assert attachment.tech_card_revision_id == 1
                assert download.filename == "private-pattern.webp"
                assert download.url.startswith("https://signed.test/garment-buro-test-crm-private/")
                assert download.url.endswith("&download=1")
                assert "cdn.test" not in download.url
                assert access_event is not None
                assert access_event.attachment_id == attachment.id
                assert access_event.actor_user_id == 1
                assert access_event.event_type == "download_url_issued"
                assert ensure_utc(access_event.occurred_at) == NOW
                assert ensure_utc(access_event.expires_at) > ensure_utc(access_event.occurred_at)
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_crm_file_rejects_active_content_and_invalid_role_target(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "crm-private-invalid.db")
        database = DatabaseManager(settings)
        client = FakeMinioClient()
        service = CrmFileService(MinioStorage(settings, client=client))
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await _seed_revision(database)
            with pytest.raises(ValueError, match="authenticated actor"):
                async with database.session() as session:
                    await service.upload(
                        session,
                        data=_webp(),
                        original_filename="pattern.webp",
                        role=CrmFileRole.PATTERN,
                        tech_card_revision_id=1,
                        actor_user_id=None,
                        now=NOW,
                    )
            with pytest.raises(ValueError, match="role is invalid"):
                async with database.session() as session:
                    await service.upload(
                        session,
                        data=_webp(),
                        original_filename="evidence.webp",
                        role=CrmFileRole.PRODUCTION_EVIDENCE,
                        tech_card_revision_id=1,
                        actor_user_id=1,
                        now=NOW,
                    )
            with pytest.raises(UnsupportedCrmFileError, match="Only PDF"):
                async with database.session() as session:
                    await service.upload(
                        session,
                        data=b"<svg><script>alert(1)</script></svg>",
                        original_filename="unsafe.svg",
                        role=CrmFileRole.PATTERN,
                        tech_card_revision_id=1,
                        actor_user_id=1,
                        now=NOW,
                    )
            assert client.uploads == []
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_crm_file_marks_metadata_failed_when_private_storage_fails(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "crm-private-failed.db")
        database = DatabaseManager(settings)
        service = CrmFileService(MinioStorage(settings, client=FailingMinioClient()))
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await _seed_revision(database)
            with pytest.raises(CrmFileStorageError, match="Private CRM storage"):
                async with database.session() as session:
                    await service.upload(
                        session,
                        data=_webp(),
                        original_filename="failed.webp",
                        role=CrmFileRole.PATTERN,
                        tech_card_revision_id=1,
                        actor_user_id=1,
                        now=NOW,
                    )
            async with database.session() as session:
                media = await session.scalar(select(MediaObject))
                attachments = list(await session.scalars(select(CrmFileAttachment)))
                assert media is not None and media.status == "failed"
                assert not media.is_public
                assert attachments == []
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_crm_file_http_is_guarded_bounded_private_and_audited(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(
            tmp_path / "crm-private-http.db",
            crm_file_max_upload_bytes=1_024,
        )
        database = DatabaseManager(settings)
        minio = FakeMinioClient()
        service = CrmFileService(MinioStorage(settings, client=minio))
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            actor = await _seed_revision(database)
            identity = StaffIdentityGate(actor)
            application = FastAPI()
            application.state.settings = settings
            application.state.database = database
            application.state.identity_service = identity
            application.state.crm_file_service = service
            application.include_router(crm_file_router)

            headers = {"Authorization": "Bearer staff-token"}
            form = {
                "role": "pattern",
                "tech_card_revision_id": "1",
                "sort_order": "0",
            }
            async with AsyncClient(
                transport=ASGITransport(app=application),
                base_url="http://test",
            ) as client:
                unauthorized = await client.get("/api/crm/files/1/download")
                assert unauthorized.status_code == 401

                denied = await client.post(
                    "/api/crm/files",
                    headers=headers,
                    data=form,
                    files={"file": ("pattern.webp", _webp(), "image/webp")},
                )
                assert denied.status_code == 403

                identity.allowed = True
                uploaded = await client.post(
                    "/api/crm/files",
                    headers=headers,
                    data=form,
                    files={
                        "file": (
                            "../pattern.webp",
                            _webp(),
                            "application/x-untrusted-client-type",
                        )
                    },
                )
                assert uploaded.status_code == 201
                assert uploaded.headers["cache-control"] == "no-store"
                body = uploaded.json()
                assert set(body) == {
                    "attachment_id",
                    "media_id",
                    "content_type",
                    "size_bytes",
                    "checksum_sha256",
                }
                assert body["content_type"] == "image/webp"
                assert body["size_bytes"] == len(_webp())
                assert len(body["checksum_sha256"]) == 64
                assert len(minio.uploads) == 1
                assert minio.uploads[0]["bucket_name"] == settings.minio_crm_bucket

                download = await client.get(
                    f"/api/crm/files/{body['attachment_id']}/download",
                    headers=headers,
                )
                assert download.status_code == 200
                assert download.headers["cache-control"] == "no-store"
                download_body = download.json()
                assert download_body["filename"] == "pattern.webp"
                assert download_body["content_type"] == "image/webp"
                assert download_body["checksum_sha256"] == body["checksum_sha256"]
                assert download_body["expires_seconds"] == 900
                assert download_body["url"].startswith(
                    "https://signed.test/garment-buro-test-crm-private/"
                )
                assert "cdn.test" not in download_body["url"]

                missing_download = await client.get(
                    "/api/crm/files/9999/download",
                    headers=headers,
                )
                assert missing_download.status_code == 404

                missing_target = await client.post(
                    "/api/crm/files",
                    headers=headers,
                    data={**form, "tech_card_revision_id": "9999", "sort_order": "1"},
                    files={"file": ("missing.webp", _webp(), "image/webp")},
                )
                assert missing_target.status_code == 404

                invalid_target_role = await client.post(
                    "/api/crm/files",
                    headers=headers,
                    data={**form, "role": "production_evidence", "sort_order": "1"},
                    files={"file": ("invalid.webp", _webp(), "image/webp")},
                )
                assert invalid_target_role.status_code == 422

                unsupported = await client.post(
                    "/api/crm/files",
                    headers=headers,
                    data={**form, "sort_order": "1"},
                    files={
                        "file": (
                            "unsafe.svg",
                            b"<svg><script>alert(1)</script></svg>",
                            "image/webp",
                        )
                    },
                )
                assert unsupported.status_code == 415

                oversized = await client.post(
                    "/api/crm/files",
                    headers=headers,
                    data={**form, "sort_order": "2"},
                    files={"file": ("too-large.pdf", b"x" * 1_025, "application/pdf")},
                )
                assert oversized.status_code == 413

                replayed_upload = await client.post(
                    "/api/crm/files",
                    headers=headers,
                    data=form,
                    files={"file": ("pattern.webp", _webp(), "image/webp")},
                )
                assert replayed_upload.status_code == 201
                assert replayed_upload.json() == uploaded.json()
                assert len(minio.uploads) == 1

                changed_slot = await client.post(
                    "/api/crm/files",
                    headers=headers,
                    data=form,
                    files={
                        "file": (
                            "pattern.webp",
                            _webp((30, 20, 10)),
                            "image/webp",
                        )
                    },
                )
                assert changed_slot.status_code == 409

                application.state.crm_file_service = CrmFileService(
                    MinioStorage(settings, client=FailingMinioClient())
                )
                unavailable_storage = await client.post(
                    "/api/crm/files",
                    headers=headers,
                    data={**form, "sort_order": "3"},
                    files={"file": ("unavailable.webp", _webp(), "image/webp")},
                )
                assert unavailable_storage.status_code == 503
                assert unavailable_storage.json() == {
                    "detail": "Private CRM storage is unavailable"
                }

            async with database.session() as session:
                attachments = list(await session.scalars(select(CrmFileAttachment)))
                access_events = list(await session.scalars(select(CrmFileAccessEvent)))
                media_objects = list(
                    await session.scalars(select(MediaObject).order_by(MediaObject.id))
                )
                assert len(attachments) == 1
                assert len(access_events) == 1
                assert access_events[0].actor_user_id == actor.id
                assert [media.status for media in media_objects] == ["ready", "failed"]
                assert all(not media.is_public for media in media_objects)
                assert minio.removed == []
                assert all(
                    permission == PermissionCode.CRM_ACCESS for permission in identity.permissions
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())
