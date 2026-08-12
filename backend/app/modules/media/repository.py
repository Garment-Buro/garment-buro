from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.minio import StoredObject
from app.modules.media.models import MediaObject, MediaStatus


class MediaRepository:
    async def get_ready_by_keys(
        self,
        session: AsyncSession,
        *,
        bucket_name: str,
        object_keys: set[str],
    ) -> dict[str, MediaObject]:
        if not object_keys:
            return {}
        result = await session.scalars(
            select(MediaObject).where(
                MediaObject.bucket_name == bucket_name,
                MediaObject.object_key.in_(object_keys),
                MediaObject.status == MediaStatus.READY.value,
            )
        )
        return {media.object_key: media for media in result}

    async def create_pending(
        self,
        session: AsyncSession,
        *,
        bucket_name: str,
        object_key: str,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        checksum_sha256: str,
        is_public: bool,
        uploaded_by_user_id: int | None = None,
    ) -> MediaObject:
        media = MediaObject(
            uploaded_by_user_id=uploaded_by_user_id,
            bucket_name=bucket_name,
            object_key=object_key,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            is_public=is_public,
            status=MediaStatus.PENDING.value,
        )
        session.add(media)
        await session.flush()
        return media

    async def mark_ready(
        self,
        session: AsyncSession,
        media: MediaObject,
        stored: StoredObject,
    ) -> None:
        media.etag = stored.etag
        media.version_id = stored.version_id
        media.status = MediaStatus.READY.value
        await session.flush()

    async def mark_failed(
        self,
        session: AsyncSession,
        media: MediaObject,
    ) -> None:
        media.status = MediaStatus.FAILED.value
        await session.flush()
