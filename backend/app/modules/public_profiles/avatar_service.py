import hashlib
import re
from functools import partial
from uuid import uuid4

from anyio import to_thread
from minio.error import S3Error
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.minio import MinioStorage
from app.modules.media.errors import PrivateStorageUnavailableError
from app.modules.media.filenames import safe_media_filename
from app.modules.media.private_images import PRIVATE_IMAGE_MAX_BYTES, prepare_private_image
from app.modules.media.private_uploads import (
    put_private_while_locked,
    require_private_customer_storage,
)
from app.modules.public_profiles.avatar_preview import render_avatar_card
from app.modules.public_profiles.avatar_repository import AvatarRepository
from app.modules.public_profiles.schemas import OwnPublicProfileResponse
from app.modules.public_profiles.service import ProfileUnavailableError, PublicProfileService

AVATAR_MAX_BYTES = 2 * 1024 * 1024


class AvatarTooLargeError(Exception):
    pass


class AvatarService:
    def __init__(self, storage: MinioStorage):
        self.storage = storage
        self.repository = AvatarRepository()
        self.profiles = PublicProfileService()

    @property
    def max_upload_bytes(self) -> int:
        return min(PRIVATE_IMAGE_MAX_BYTES, self.storage.settings.media_max_upload_bytes)

    async def upload(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        expected_version: int,
        data: bytes,
        original_filename: str,
    ) -> OwnPublicProfileResponse:
        if len(data) > self.max_upload_bytes:
            raise AvatarTooLargeError
        prepared = await to_thread.run_sync(
            partial(prepare_private_image, data, max_output_side=512)
        )
        if len(prepared) > min(AVATAR_MAX_BYTES, self.max_upload_bytes):
            raise AvatarTooLargeError
        await require_private_customer_storage(self.storage)
        await self.profiles.lock_owned(session, user_id, expected_version, must_exist=True)
        media = await self.repository.create_pending(
            session,
            bucket_name=self.storage.settings.minio_customer_projects_bucket,
            object_key=f"profiles/{user_id}/{uuid4().hex}.webp",
            original_filename=safe_media_filename(original_filename),
            content_type="image/webp",
            size_bytes=len(prepared),
            checksum_sha256=hashlib.sha256(prepared).hexdigest(),
            is_public=False,
            uploaded_by_user_id=user_id,
        )
        await session.commit()
        # Re-read version after the durable intent; another request may have saved.
        profile = await self.profiles.lock_owned(
            session, user_id, expected_version, must_exist=True
        )
        media = await self.repository.lock_pending(session, media_id=media.id)
        if media is None:
            raise PrivateStorageUnavailableError("Avatar upload is no longer pending")
        await require_private_customer_storage(self.storage)
        try:
            stored = await put_private_while_locked(
                self.storage, object_key=media.object_key, data=prepared, content_type="image/webp"
            )
        except Exception:
            try:
                await self.repository.mark_failed(session, media)
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
            raise
        await self.repository.mark_ready(session, media, stored)
        assert profile is not None
        await self.profiles.repository.detach_avatar(session, profile)
        profile.avatar_media_id = media.id
        profile.version += 1
        await session.flush()
        result = OwnPublicProfileResponse.model_validate(profile)
        await session.commit()
        return result

    async def read(
        self,
        session: AsyncSession,
        *,
        media_id: int,
        user_id: int | None = None,
        slug: str | None = None,
        card_preview: bool = False,
    ) -> bytes:
        media = await self.repository.current_object(
            session,
            media_id=media_id,
            bucket_name=self.storage.settings.minio_customer_projects_bucket,
            user_id=user_id,
            slug=slug,
        )
        if media is None or not re.fullmatch(
            rf"profiles/{media['user_id']}/[0-9a-f]{{32}}\.webp", media["object_key"]
        ):
            raise ProfileUnavailableError
        if not 0 < media["size_bytes"] <= min(AVATAR_MAX_BYTES, self.max_upload_bytes):
            raise PrivateStorageUnavailableError("Avatar size is unavailable")
        await require_private_customer_storage(self.storage)
        try:
            data = await self.storage.read_private_customer_object(
                media["object_key"], max_bytes=media["size_bytes"], version_id=media["version_id"]
            )
        except S3Error as error:
            if error.code in {"NoSuchKey", "NoSuchObject", "NoSuchVersion"}:
                raise ProfileUnavailableError from error
            raise
        if (
            len(data) != media["size_bytes"]
            or hashlib.sha256(data).hexdigest() != media["checksum_sha256"]
        ):
            raise PrivateStorageUnavailableError("Avatar contents are unavailable")
        # Existing files use the same canonical bytes; no re-upload or stored derivative.
        return await to_thread.run_sync(render_avatar_card, data) if card_preview else data
