from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from anyio import to_thread
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.minio import MinioStorage
from app.modules.crm.file_models import CrmFileAccessEvent, CrmFileAttachment, CrmFileRole
from app.modules.crm.file_repository import CrmFileRepository
from app.modules.identity.security import ensure_utc
from app.modules.media.models import MediaObject, MediaStatus
from app.modules.media.repository import MediaRepository

CRM_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


@dataclass(frozen=True, slots=True)
class PreparedCrmFile:
    data: bytes
    content_type: str
    extension: str


@dataclass(frozen=True, slots=True)
class CrmFileUploadResult:
    attachment_id: int
    media_id: int
    content_type: str
    size_bytes: int
    checksum_sha256: str


@dataclass(frozen=True, slots=True)
class CrmFileDownload:
    attachment_id: int
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    expires_seconds: int
    url: str


class CrmFileNotFoundError(LookupError):
    pass


class UnsupportedCrmFileError(ValueError):
    pass


class CrmFileConflictError(ValueError):
    pass


class CrmFileStorageError(RuntimeError):
    pass


def prepare_crm_file(data: bytes) -> PreparedCrmFile:
    if not data:
        raise UnsupportedCrmFileError("Uploaded CRM file is empty")
    if data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]:
        return PreparedCrmFile(data=data, content_type="application/pdf", extension=".pdf")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                image.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        image_format = None
    if image_format in CRM_IMAGE_FORMATS:
        content_type, extension = CRM_IMAGE_FORMATS[image_format]
        return PreparedCrmFile(data=data, content_type=content_type, extension=extension)
    raise UnsupportedCrmFileError("Only PDF, JPEG, PNG, and WebP CRM files are supported")


class CrmFileService:
    def __init__(
        self,
        storage: MinioStorage,
        *,
        repository: CrmFileRepository | None = None,
        media_repository: MediaRepository | None = None,
    ) -> None:
        self.storage = storage
        self.repository = repository or CrmFileRepository()
        self.media_repository = media_repository or MediaRepository()

    async def upload(
        self,
        session: AsyncSession,
        *,
        data: bytes,
        original_filename: str,
        role: CrmFileRole,
        tech_card_revision_id: int | None = None,
        production_project_id: int | None = None,
        production_unit_id: int | None = None,
        sort_order: int = 0,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmFileUploadResult:
        self._require_actor(actor_user_id)
        self._validate_target(
            role=role,
            tech_card_revision_id=tech_card_revision_id,
            production_project_id=production_project_id,
            production_unit_id=production_unit_id,
            sort_order=sort_order,
        )
        if len(data) > self.storage.settings.crm_file_max_upload_bytes:
            raise ValueError("Upload exceeds CRM_FILE_MAX_UPLOAD_BYTES")
        if not await self.repository.target_exists(
            session,
            tech_card_revision_id=tech_card_revision_id,
            production_project_id=production_project_id,
            production_unit_id=production_unit_id,
        ):
            raise CrmFileNotFoundError("CRM file target was not found")
        prepared = await to_thread.run_sync(prepare_crm_file, data)
        checksum = hashlib.sha256(prepared.data).hexdigest()
        safe_filename = self._safe_filename(original_filename)
        existing = await self.repository.get_attachment_for_slot(
            session,
            role=role.value,
            tech_card_revision_id=tech_card_revision_id,
            production_project_id=production_project_id,
            production_unit_id=production_unit_id,
            sort_order=sort_order,
        )
        if existing is not None:
            return self._replay_upload(
                existing,
                checksum_sha256=checksum,
                original_filename=safe_filename,
                actor_user_id=actor_user_id,
            )
        object_key = self._object_key(role, prepared.extension, now)
        media = await self.media_repository.create_pending(
            session,
            bucket_name=self.storage.settings.minio_crm_bucket,
            object_key=object_key,
            original_filename=safe_filename,
            content_type=prepared.content_type,
            size_bytes=len(prepared.data),
            checksum_sha256=checksum,
            is_public=False,
            uploaded_by_user_id=actor_user_id,
        )
        await session.commit()
        try:
            stored = await self.storage.put_private_crm_object(
                object_key=object_key,
                data=prepared.data,
                content_type=prepared.content_type,
            )
        except Exception as error:
            await self._mark_failed(session, media)
            raise CrmFileStorageError("Private CRM storage is unavailable") from error
        try:
            await self.media_repository.mark_ready(session, media, stored)
            attachment = CrmFileAttachment(
                media_object_id=media.id,
                tech_card_revision_id=tech_card_revision_id,
                production_project_id=production_project_id,
                production_unit_id=production_unit_id,
                role=role.value,
                sort_order=sort_order,
                uploaded_by_user_id=actor_user_id,
                created_at=ensure_utc(now or datetime.now(timezone.utc)),
            )
            await self.repository.add_attachment(session, attachment)
            await session.commit()
        except Exception as error:
            await session.rollback()
            try:
                await self.storage.remove_private_crm_object(object_key)
            except Exception:  # noqa: BLE001 - best effort; preserve the database failure.
                pass
            await self._mark_failed(session, media)
            if isinstance(error, IntegrityError):
                existing = await self.repository.get_attachment_for_slot(
                    session,
                    role=role.value,
                    tech_card_revision_id=tech_card_revision_id,
                    production_project_id=production_project_id,
                    production_unit_id=production_unit_id,
                    sort_order=sort_order,
                )
                if existing is not None:
                    return self._replay_upload(
                        existing,
                        checksum_sha256=checksum,
                        original_filename=safe_filename,
                        actor_user_id=actor_user_id,
                    )
                raise CrmFileConflictError("CRM file slot is already occupied") from error
            raise
        return CrmFileUploadResult(
            attachment_id=attachment.id,
            media_id=media.id,
            content_type=media.content_type,
            size_bytes=media.size_bytes,
            checksum_sha256=media.checksum_sha256,
        )

    async def get_download(
        self,
        session: AsyncSession,
        *,
        attachment_id: int,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> CrmFileDownload:
        self._require_actor(actor_user_id)
        attachment = await self.repository.get_ready_attachment(
            session,
            attachment_id=attachment_id,
        )
        if attachment is None:
            raise CrmFileNotFoundError("CRM file was not found")
        media = attachment.media
        if media.is_public or media.bucket_name != self.storage.settings.minio_crm_bucket:
            raise CrmFileNotFoundError("CRM file storage evidence is invalid")
        filename = media.original_filename or "download"
        try:
            url = await self.storage.presigned_crm_get_url(
                media.object_key,
                filename=filename,
            )
        except Exception as error:
            raise CrmFileStorageError("Private CRM storage is unavailable") from error
        occurred_at = ensure_utc(now or datetime.now(timezone.utc))
        await self.repository.add_access_event(
            session,
            CrmFileAccessEvent(
                attachment_id=attachment.id,
                event_type="download_url_issued",
                actor_user_id=actor_user_id,
                occurred_at=occurred_at,
                expires_at=occurred_at
                + timedelta(seconds=self.storage.settings.minio_presigned_expire_seconds),
            ),
        )
        await session.commit()
        return CrmFileDownload(
            attachment_id=attachment.id,
            filename=filename,
            content_type=media.content_type,
            size_bytes=media.size_bytes,
            checksum_sha256=media.checksum_sha256,
            expires_seconds=self.storage.settings.minio_presigned_expire_seconds,
            url=url,
        )

    async def _mark_failed(self, session: AsyncSession, media: MediaObject) -> None:
        try:
            media.status = MediaStatus.FAILED.value
            await session.flush()
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()

    def _replay_upload(
        self,
        attachment: CrmFileAttachment,
        *,
        checksum_sha256: str,
        original_filename: str,
        actor_user_id: int,
    ) -> CrmFileUploadResult:
        media = attachment.media
        if (
            attachment.uploaded_by_user_id != actor_user_id
            or media.status != MediaStatus.READY.value
            or media.is_public
            or media.bucket_name != self.storage.settings.minio_crm_bucket
            or media.checksum_sha256 != checksum_sha256
            or media.original_filename != original_filename
        ):
            raise CrmFileConflictError("CRM file slot is already occupied")
        return CrmFileUploadResult(
            attachment_id=attachment.id,
            media_id=media.id,
            content_type=media.content_type,
            size_bytes=media.size_bytes,
            checksum_sha256=media.checksum_sha256,
        )

    @staticmethod
    def _validate_target(
        *,
        role: CrmFileRole,
        tech_card_revision_id: int | None,
        production_project_id: int | None,
        production_unit_id: int | None,
        sort_order: int,
    ) -> None:
        targets = (
            tech_card_revision_id,
            production_project_id,
            production_unit_id,
        )
        if sum(value is not None for value in targets) != 1 or any(
            value is not None and value <= 0 for value in targets
        ):
            raise ValueError("CRM file requires exactly one valid target")
        if sort_order < 0:
            raise ValueError("CRM file sort order must not be negative")
        if tech_card_revision_id is not None and role not in {
            CrmFileRole.PATTERN,
            CrmFileRole.TECH_CARD_SOURCE,
        }:
            raise ValueError("CRM tech-card revision file role is invalid")
        if tech_card_revision_id is None and role != CrmFileRole.PRODUCTION_EVIDENCE:
            raise ValueError("CRM production file role is invalid")

    @staticmethod
    def _object_key(role: CrmFileRole, extension: str, now: datetime | None) -> str:
        current = ensure_utc(now or datetime.now(timezone.utc))
        return f"crm/{role.value}/{current:%Y/%m/%d}/{uuid4().hex}{extension}"

    @staticmethod
    def _safe_filename(filename: str) -> str:
        basename = Path((filename or "upload").replace("\\", "/")).name
        printable = "".join(character for character in basename if character.isprintable())
        return (printable.strip() or "upload")[:255]

    @staticmethod
    def _require_actor(actor_user_id: int | None) -> None:
        if actor_user_id is None or actor_user_id <= 0:
            raise ValueError("CRM file operation requires an authenticated actor")
