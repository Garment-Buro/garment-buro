from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from anyio import to_thread
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.minio import MinioStorage
from app.modules.crm.file_service import UnsupportedCrmFileError, prepare_crm_file
from app.modules.media.repository import MediaRepository


@dataclass(frozen=True, slots=True)
class AssortmentMediaReceipt:
    media_id: int
    original_filename: str
    content_type: str
    size_bytes: int


class AssortmentMediaService:
    """Store private pattern files without creating a production attachment."""

    def __init__(
        self,
        storage: MinioStorage,
        repository: MediaRepository | None = None,
    ) -> None:
        self.storage = storage
        self.repository = repository or MediaRepository()

    async def upload_pattern(
        self,
        session: AsyncSession,
        *,
        data: bytes,
        original_filename: str,
        actor_user_id: int,
    ) -> AssortmentMediaReceipt:
        if len(data) > self.storage.settings.crm_file_max_upload_bytes:
            raise ValueError("Upload exceeds CRM_FILE_MAX_UPLOAD_BYTES")
        prepared = await to_thread.run_sync(prepare_crm_file, data)
        checksum = hashlib.sha256(prepared.data).hexdigest()
        safe_filename = self._safe_filename(original_filename)
        object_key = (
            f"assortment/patterns/{datetime.now(timezone.utc):%Y/%m/%d}/"
            f"{uuid4().hex}{prepared.extension}"
        )
        media = await self.repository.create_pending(
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
        except Exception:
            try:
                await self.repository.mark_failed(session, media)
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
            raise
        await self.repository.mark_ready(session, media, stored)
        await session.commit()
        return AssortmentMediaReceipt(
            media_id=media.id,
            original_filename=safe_filename,
            content_type=media.content_type,
            size_bytes=media.size_bytes,
        )

    @staticmethod
    def _safe_filename(filename: str) -> str:
        basename = Path((filename or "pattern").replace("\\", "/")).name
        printable = "".join(character for character in basename if character.isprintable())
        return (printable.strip() or "pattern")[:255]


__all__ = [
    "AssortmentMediaReceipt",
    "AssortmentMediaService",
    "UnsupportedCrmFileError",
]
