import hashlib
import re
from datetime import datetime, timedelta
from uuid import uuid4

from anyio import to_thread
from minio.error import S3Error
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.minio import MinioStorage
from app.modules.design_assets.models import DesignAsset
from app.modules.design_assets.repository import DesignAssetRepository
from app.modules.design_assets.schemas import DesignImage, ImportedDesignImage, ImportedDesignImages
from app.modules.design_assets.security import (
    DesignAssetUnavailableError,
    create_design_asset_token,
    design_asset_path,
    digest_design_asset_token,
)
from app.modules.identity.customer_writes import lock_active_customer
from app.modules.identity.security import ensure_utc
from app.modules.media.errors import PrivateStorageUnavailableError
from app.modules.media.models import MediaObject
from app.modules.media.private_images import PRIVATE_IMAGE_MAX_BYTES, prepare_private_image
from app.modules.media.private_uploads import (
    put_private_while_locked,
    require_private_customer_storage,
)
from app.modules.media.repository import MediaRepository

DESIGN_ASSET_TTL = timedelta(days=7)
PRIVATE_DESIGN_KEY = re.compile(r"^(?:designs|projects/[1-9][0-9]*)/[0-9a-f]{32}\.webp$")


class DesignImageTooLargeError(ValueError):
    pass


class DesignMediaService:
    def __init__(self, storage: MinioStorage):
        self.storage = storage
        self.repository = DesignAssetRepository()
        self.media = MediaRepository()

    @property
    def max_upload_bytes(self) -> int:
        return min(PRIVATE_IMAGE_MAX_BYTES, self.storage.settings.media_max_upload_bytes)

    def create_reference(
        self, session: AsyncSession, media: MediaObject, now: datetime
    ) -> DesignImage:
        token = create_design_asset_token()
        expiry = ensure_utc(now) + DESIGN_ASSET_TTL
        session.add(
            DesignAsset(
                media_object_id=media.id,
                access_digest_sha256=digest_design_asset_token(token),
                expires_at=expiry,
            )
        )
        return DesignImage(
            url=design_asset_path(token),
            content_type=media.content_type,
            size_bytes=media.size_bytes,
            expires_at=expiry,
        )

    async def upload(self, session: AsyncSession, *, data: bytes, now: datetime) -> DesignImage:
        if len(data) > self.max_upload_bytes:
            raise DesignImageTooLargeError
        prepared = await to_thread.run_sync(prepare_private_image, data)
        if len(prepared) > self.max_upload_bytes:
            raise DesignImageTooLargeError
        await require_private_customer_storage(self.storage)
        media = await self.media.create_pending(
            session,
            bucket_name=self.storage.settings.minio_customer_projects_bucket,
            object_key=f"designs/{uuid4().hex}.webp",
            original_filename="design.webp",
            content_type="image/webp",
            size_bytes=len(prepared),
            checksum_sha256=hashlib.sha256(prepared).hexdigest(),
            is_public=False,
        )
        media_id = media.id
        # An interrupted PUT leaves a durable pending intent for the worker.
        await session.commit()
        media = await self.media.lock_pending(session, media_id=media_id)
        if media is None:
            raise PrivateStorageUnavailableError("Upload is no longer pending")
        try:
            await require_private_customer_storage(self.storage)
            stored = await put_private_while_locked(
                self.storage, object_key=media.object_key, data=prepared, content_type="image/webp"
            )
        except Exception:
            try:
                await self.media.mark_failed(session, media)
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
            raise
        await self.media.mark_ready(session, media, stored)
        result = self.create_reference(session, media, now)
        await session.commit()
        return result

    async def import_owned(
        self, session: AsyncSession, *, user_id: int, media_ids: list[int], now: datetime
    ) -> ImportedDesignImages:
        if not 1 <= len(media_ids) <= 102 or any(
            not 0 < item <= 2_147_483_647 for item in media_ids
        ):
            raise DesignAssetUnavailableError("Design image is unavailable")
        if not await lock_active_customer(session, user_id):
            raise DesignAssetUnavailableError("Design image is unavailable")
        media = await self.repository.lock_owned_media(
            session,
            user_id=user_id,
            media_ids=media_ids,
            bucket_name=self.storage.settings.minio_customer_projects_bucket,
        )
        if any(
            not PRIVATE_DESIGN_KEY.fullmatch(item.object_key)
            or not 0 < item.size_bytes <= self.max_upload_bytes
            for item in media
        ):
            raise DesignAssetUnavailableError("Design image is unavailable")
        await require_private_customer_storage(self.storage)
        result = ImportedDesignImages(
            items=[
                ImportedDesignImage(
                    media_id=item.id, **self.create_reference(session, item, now).model_dump()
                )
                for item in media
            ]
        )
        await session.commit()
        return result

    async def read(self, session: AsyncSession, *, token: str, now: datetime) -> tuple[bytes, str]:
        media = await self.repository.available_media(
            session,
            token=token,
            bucket_name=self.storage.settings.minio_customer_projects_bucket,
            now=now,
        )
        if not PRIVATE_DESIGN_KEY.fullmatch(media.object_key):
            raise DesignAssetUnavailableError("Design image is unavailable")
        if not 0 < media.size_bytes <= self.max_upload_bytes:
            raise PrivateStorageUnavailableError("Design image size is unavailable")
        key, size, checksum, version, mime = (
            media.object_key,
            media.size_bytes,
            media.checksum_sha256,
            media.version_id,
            media.content_type,
        )
        # The immutable object is protected by retention; do not hold SQL resources during GET.
        await session.commit()
        await require_private_customer_storage(self.storage)
        try:
            data = await self.storage.read_private_customer_object(
                key, max_bytes=size, version_id=version
            )
        except S3Error as error:
            if error.code in {"NoSuchKey", "NoSuchObject", "NoSuchVersion"}:
                raise DesignAssetUnavailableError("Design image is unavailable") from error
            raise
        if len(data) != size or hashlib.sha256(data).hexdigest() != checksum:
            raise PrivateStorageUnavailableError("Design image contents are unavailable")
        return data, mime
