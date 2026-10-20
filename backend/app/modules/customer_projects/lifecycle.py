from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from minio.error import S3Error
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from urllib3.exceptions import HTTPError

from app.integrations.minio import MinioStorage
from app.modules.customer_projects.lifecycle_repository import ProjectLifecycleRepository
from app.modules.design_assets.repository import DesignAssetRepository
from app.modules.identity.security import ensure_utc
from app.modules.media.errors import PrivateStorageUnavailableError
from app.modules.media.models import MediaObject, MediaStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProjectMediaCleanupResult:
    media_id: int
    status: str


class ProjectMediaReconciler:
    def __init__(
        self,
        storage: MinioStorage,
        *,
        stale_upload_age: timedelta = timedelta(hours=1),
        unattached_age: timedelta = timedelta(days=7),
        retry_delay: timedelta = timedelta(minutes=1),
    ) -> None:
        if min(stale_upload_age, unattached_age, retry_delay) <= timedelta(0):
            raise ValueError("Project media cleanup intervals must be positive")
        self.storage = storage
        self.repository = ProjectLifecycleRepository()
        self.stale_upload_age = stale_upload_age
        self.unattached_age = unattached_age
        self.retry_delay = retry_delay

    async def prune_design_assets(
        self, session: AsyncSession, *, now: datetime, limit: int, dry_run: bool = False
    ) -> int:
        media_ids = await DesignAssetRepository().prune_expired(
            session, now=ensure_utc(now), limit=limit, dry_run=dry_run
        )
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
        return len(media_ids)

    async def purge_deleted_data(
        self, session: AsyncSession, *, limit: int, dry_run: bool = False
    ) -> tuple[int, int, int]:
        if not 1 <= limit <= 1000:
            raise ValueError("Cleanup batch size must be between 1 and 1000")
        counts = await self.repository.purge_deleted_data(session, limit=limit, dry_run=dry_run)
        await session.commit()
        return counts

    async def process_once(
        self,
        session: AsyncSession,
        *,
        now: datetime,
        dry_run: bool = False,
        candidate_id: int | None = None,
    ) -> ProjectMediaCleanupResult | None:
        now = ensure_utc(now)
        media = await self.repository.next_candidate(
            session,
            bucket_name=self.storage.settings.minio_customer_projects_bucket,
            now=now,
            stale_upload_age=self.stale_upload_age,
            unattached_age=self.unattached_age,
            retry_delay=self.retry_delay,
            candidate_id=candidate_id,
        )
        if media is None:
            return None
        media_id = media.id
        if await self.repository.is_referenced(session, media.id):
            await session.rollback()
            return ProjectMediaCleanupResult(media_id, "referenced")
        if dry_run:
            await session.rollback()
            return ProjectMediaCleanupResult(media_id, "candidate")
        if (await self.storage.get_private_customer_bucket_policy() or "").strip():
            raise PrivateStorageUnavailableError("Project storage must be private")
        media_id, object_key = media.id, media.object_key
        # Committed tombstone prevents attachment and survives an interrupted S3 delete.
        media.status = MediaStatus.DELETED.value
        media.updated_at = now
        await session.commit()
        try:
            await self.storage.remove_private_customer_object(object_key)
        except (HTTPError, OSError, S3Error):
            logger.warning(
                "Private project media deletion will be retried", extra={"media_id": media_id}
            )
            return ProjectMediaCleanupResult(media_id, "retry")
        await session.execute(
            delete(MediaObject).where(
                MediaObject.id == media_id,
                MediaObject.status == MediaStatus.DELETED.value,
            )
        )
        await session.commit()
        return ProjectMediaCleanupResult(media_id, "deleted")

    async def candidate_ids(self, session: AsyncSession, *, now: datetime, limit: int) -> list[int]:
        if not 1 <= limit <= 1000:
            raise ValueError("Cleanup batch size must be between 1 and 1000")
        return await self.repository.candidate_ids(
            session,
            limit=limit,
            bucket_name=self.storage.settings.minio_customer_projects_bucket,
            now=ensure_utc(now),
            stale_upload_age=self.stale_upload_age,
            unattached_age=self.unattached_age,
            retry_delay=self.retry_delay,
        )
