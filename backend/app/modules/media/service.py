from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from anyio import to_thread
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.minio import MinioStorage
from app.modules.media.models import MediaObject
from app.modules.media.repository import MediaRepository
from image_optimization import optimize_image_bytes

IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


@dataclass(frozen=True, slots=True)
class PreparedMedia:
    data: bytes
    content_type: str
    extension: str


@dataclass(frozen=True, slots=True)
class MediaUploadResult:
    media_id: int
    object_key: str
    public_url: str
    content_type: str
    size_bytes: int
    checksum_sha256: str


class UnsupportedMediaError(ValueError):
    pass


def prepare_catalog_media(data: bytes) -> PreparedMedia:
    if not data:
        raise UnsupportedMediaError("Uploaded media is empty")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                image.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        image_format = None

    if image_format in IMAGE_FORMATS:
        content_type, extension = IMAGE_FORMATS[image_format]
        if image_format in {"JPEG", "PNG"}:
            optimized = optimize_image_bytes(data)
            if optimized is not None:
                return PreparedMedia(
                    data=optimized,
                    content_type="image/webp",
                    extension=".webp",
                )
        return PreparedMedia(data=data, content_type=content_type, extension=extension)

    if len(data) >= 12 and data[4:8] == b"ftyp":
        return PreparedMedia(data=data, content_type="video/mp4", extension=".mp4")

    if data.startswith(b"\x1aE\xdf\xa3"):
        return PreparedMedia(data=data, content_type="video/webm", extension=".webm")

    raise UnsupportedMediaError("Only JPEG, PNG, WebP, MP4, and WebM media is supported")


class MediaService:
    """Persist upload intent before writing an object, then finalize its metadata."""

    def __init__(
        self,
        storage: MinioStorage,
        repository: MediaRepository | None = None,
    ) -> None:
        self.storage = storage
        self.repository = repository or MediaRepository()

    async def upload_catalog_media(
        self,
        session: AsyncSession,
        *,
        data: bytes,
        original_filename: str,
        actor_user_id: int | None = None,
    ) -> MediaUploadResult:
        if len(data) > self.storage.settings.media_max_upload_bytes:
            raise ValueError("Upload exceeds MEDIA_MAX_UPLOAD_BYTES")

        prepared = await to_thread.run_sync(prepare_catalog_media, data)
        checksum_sha256 = hashlib.sha256(prepared.data).hexdigest()
        object_key = self._new_object_key(prepared.extension)
        safe_filename = self._safe_filename(original_filename)

        media = await self.repository.create_pending(
            session,
            bucket_name=self.storage.settings.minio_media_bucket,
            object_key=object_key,
            original_filename=safe_filename,
            content_type=prepared.content_type,
            size_bytes=len(prepared.data),
            checksum_sha256=checksum_sha256,
            is_public=True,
            uploaded_by_user_id=actor_user_id,
        )
        await session.commit()

        try:
            stored = await self.storage.put_object(
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
        if stored.public_url is None:
            raise RuntimeError("Public media upload did not produce a public URL")
        return self._result(media, stored.public_url)

    @staticmethod
    def _new_object_key(extension: str) -> str:
        today = datetime.now(timezone.utc)
        return f"catalog/{today:%Y/%m/%d}/{uuid4().hex}{extension}"

    @staticmethod
    def _safe_filename(filename: str) -> str:
        basename = Path((filename or "upload").replace("\\", "/")).name
        printable = "".join(character for character in basename if character.isprintable())
        return (printable.strip() or "upload")[:255]

    @staticmethod
    def _result(media: MediaObject, public_url: str) -> MediaUploadResult:
        if media.id is None:
            raise RuntimeError("Media metadata has no database ID")
        return MediaUploadResult(
            media_id=media.id,
            object_key=media.object_key,
            public_url=public_url,
            content_type=media.content_type,
            size_bytes=media.size_bytes,
            checksum_sha256=media.checksum_sha256,
        )
