from __future__ import annotations

import hashlib
from uuid import uuid4

from anyio import to_thread
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.minio import MinioStorage
from app.modules.customer_projects.media_repository import ProjectMediaRepository
from app.modules.customer_projects.media_schemas import (
    ProjectImage,
    ProjectImageAccess,
    ProjectImages,
    ResolvedProjectImage,
)
from app.modules.customer_projects.service import (
    ProjectConflictError,
    ProjectMediaError,
    ProjectNotFoundError,
)
from app.modules.identity.customer_writes import lock_active_customer
from app.modules.media.errors import PrivateStorageUnavailableError
from app.modules.media.filenames import safe_media_filename
from app.modules.media.private_images import PRIVATE_IMAGE_MAX_BYTES, prepare_private_image
from app.modules.media.private_uploads import (
    put_private_while_locked,
    require_private_customer_storage,
)
from app.modules.media.urls import public_media_url


class ProjectMediaService:
    def __init__(self, storage: MinioStorage, repository: ProjectMediaRepository | None = None):
        self.storage = storage
        self.repository = repository or ProjectMediaRepository()

    @property
    def max_upload_bytes(self) -> int:
        return min(PRIVATE_IMAGE_MAX_BYTES, self.storage.settings.media_max_upload_bytes)

    async def upload(
        self, session: AsyncSession, *, user_id: int, data: bytes, original_filename: str
    ) -> ProjectImage:
        if len(data) > self.max_upload_bytes:
            raise ValueError("Project image exceeds upload limit")
        prepared = await to_thread.run_sync(prepare_private_image, data)
        if len(prepared) > self.max_upload_bytes:
            raise ValueError("Prepared project image exceeds upload limit")
        await require_private_customer_storage(self.storage)
        if not await lock_active_customer(session, user_id):
            raise ProjectNotFoundError
        media = await self.repository.create_pending(
            session,
            bucket_name=self.storage.settings.minio_customer_projects_bucket,
            object_key=f"projects/{user_id}/{uuid4().hex}.webp",
            original_filename=safe_media_filename(original_filename),
            content_type="image/webp",
            size_bytes=len(prepared),
            checksum_sha256=hashlib.sha256(prepared).hexdigest(),
            is_public=False,
            uploaded_by_user_id=user_id,
        )
        # A durable pending row permits reconciliation after an interrupted object write.
        await session.commit()
        if not await lock_active_customer(session, user_id):
            raise ProjectNotFoundError
        media = await self.repository.lock_pending(session, media_id=media.id)
        if media is None:
            raise PrivateStorageUnavailableError("Upload is no longer pending")
        # Keep the row lock until PUT/ready commits; cleanup skips an active upload.
        try:
            stored = await put_private_while_locked(
                self.storage,
                object_key=media.object_key,
                data=prepared,
                content_type=media.content_type,
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
        return ProjectImage(
            id=media.id, content_type=media.content_type, size_bytes=media.size_bytes
        )

    async def access(
        self, session: AsyncSession, *, user_id: int, media_id: int
    ) -> ProjectImageAccess:
        media = await self.repository.get_owned_ready(
            session,
            user_id=user_id,
            media_id=media_id,
            bucket_name=self.storage.settings.minio_customer_projects_bucket,
        )
        if media is None:
            raise ProjectNotFoundError
        await require_private_customer_storage(self.storage)
        url = await self.storage.presigned_project_get_url(
            media.object_key, content_type=media.content_type
        )
        return ProjectImageAccess(
            id=media.id,
            content_type=media.content_type,
            size_bytes=media.size_bytes,
            url=url,
            expires_in=self.storage.settings.minio_presigned_expire_seconds,
        )

    async def project_images(
        self, session: AsyncSession, *, user_id: int, project_id: int, version: int
    ) -> ProjectImages:
        media = await self.repository.get_project_images(
            session,
            user_id=user_id,
            project_id=project_id,
            version=version,
        )
        if not media:
            current = await self.repository.get_project_version(
                session,
                user_id=user_id,
                project_id=project_id,
            )
            if current is None:
                raise ProjectNotFoundError
            if current != version:
                raise ProjectConflictError
            raise ProjectMediaError
        private = [item for item in media if not item.is_public]
        if any(
            item.uploaded_by_user_id != user_id
            or item.bucket_name != self.storage.settings.minio_customer_projects_bucket
            or not item.object_key.startswith(f"projects/{user_id}/")
            for item in private
        ):
            raise ProjectMediaError
        if any(
            item.status != "ready"
            or item.content_type not in {"image/jpeg", "image/png", "image/webp"}
            for item in media
        ):
            raise ProjectMediaError
        if private:
            await require_private_customer_storage(self.storage)
        resolved = []
        for item in media:
            url = (
                public_media_url(self.storage.settings, item)
                if item.is_public
                else await self.storage.presigned_project_get_url(
                    item.object_key,
                    content_type=item.content_type,
                )
            )
            resolved.append(
                ResolvedProjectImage(
                    id=item.id,
                    content_type=item.content_type,
                    size_bytes=item.size_bytes,
                    url=url,
                    expires_in=None
                    if item.is_public
                    else self.storage.settings.minio_presigned_expire_seconds,
                )
            )
        return ProjectImages(version=version, items=resolved)
