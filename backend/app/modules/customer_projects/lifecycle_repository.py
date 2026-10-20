from __future__ import annotations

from datetime import datetime, timedelta
from typing import TypedDict, Unpack

from sqlalchemy import Select, delete, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.base import Base
from app.modules.customer_projects.models import CustomerProject
from app.modules.favorites.models import UserFavorite
from app.modules.identity.models import User, UserStatus
from app.modules.media.models import MediaObject, MediaStatus
from app.modules.partners.community_favorite_models import UserCommunityFavorite
from app.modules.public_profiles.models import PublicUserProfile


class CleanupCriteria(TypedDict):
    bucket_name: str
    now: datetime
    stale_upload_age: timedelta
    unattached_age: timedelta
    retry_delay: timedelta


def has_references() -> ColumnElement[bool]:
    # The schema is the source of truth, including nullable SET NULL references
    # and future modules with differently named media FK columns.
    return or_(
        *(
            exists(select(column).where(column == MediaObject.id))
            for table in Base.metadata.tables.values()
            for column in table.columns
            if any(fk.target_fullname == "media_objects.id" for fk in column.foreign_keys)
        )
    )


class ProjectLifecycleRepository:
    def _candidate_queries(
        self,
        *,
        bucket_name: str,
        now: datetime,
        stale_upload_age: timedelta,
        unattached_age: timedelta,
        retry_delay: timedelta,
    ) -> tuple[Select[tuple[MediaObject]], ...]:
        base = select(MediaObject).where(
            MediaObject.provider == "minio",
            MediaObject.bucket_name == bucket_name,
            MediaObject.is_public.is_(False),
            MediaObject.object_key.regexp_match(
                r"^((projects|profiles)/[1-9][0-9]*|designs)/[0-9a-f]{32}\.webp$"
            ),
            ~has_references(),
        )
        # One status and one age range let PostgreSQL use the lifecycle index.
        # A single OR across statuses/owners forces a scan and sort of fresh files.
        aged = tuple(
            base.where(MediaObject.status == status, MediaObject.updated_at <= now - age)
            for status, age in (
                (MediaStatus.DELETED.value, retry_delay),
                (MediaStatus.FAILED.value, stale_upload_age),
                (MediaStatus.PENDING.value, stale_upload_age),
                (MediaStatus.READY.value, unattached_age),
            )
        )
        ready = base.where(MediaObject.status == MediaStatus.READY.value)
        return (
            *aged,
            ready.join(User, User.id == MediaObject.uploaded_by_user_id).where(
                User.status == UserStatus.DELETED.value
            ),
            ready.where(MediaObject.uploaded_by_user_id.is_(None)),
        )

    async def candidate_ids(
        self, session: AsyncSession, *, limit: int, **criteria: Unpack[CleanupCriteria]
    ) -> list[int]:
        ids: list[int] = []
        for query in self._candidate_queries(**criteria):
            ids.extend(
                await session.scalars(
                    query.with_only_columns(MediaObject.id)
                    .where(MediaObject.id.not_in(ids))
                    .order_by(MediaObject.updated_at, MediaObject.id)
                    .limit(limit - len(ids))
                    .with_for_update(skip_locked=True, of=MediaObject)
                )
            )
            if len(ids) == limit:
                break
        return ids

    async def next_candidate(
        self,
        session: AsyncSession,
        *,
        candidate_id: int | None = None,
        **criteria: Unpack[CleanupCriteria],
    ) -> MediaObject | None:
        queries = self._candidate_queries(**criteria)
        if candidate_id is not None:
            # First acquire the lock, then obtain a fresh READ COMMITTED snapshot.
            # EXISTS InitPlans in the locking statement can otherwise cache an
            # old eligibility result even when EvalPlanQual rereads the row.
            media = await session.scalar(
                select(MediaObject)
                .where(MediaObject.id == candidate_id)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
            if media is None:
                return None
            eligible = or_(
                *(exists(query.where(MediaObject.id == candidate_id)) for query in queries)
            )
            return media if await session.scalar(select(eligible)) else None
        for query in queries:
            media = await session.scalar(
                query.order_by(MediaObject.updated_at, MediaObject.id)
                .limit(1)
                .with_for_update(skip_locked=True, of=MediaObject)
                .execution_options(populate_existing=True)
            )
            if media is not None:
                return media
        return None

    async def is_referenced(self, session: AsyncSession, media_id: int) -> bool:
        # A fresh READ COMMITTED statement closes the snapshot-to-row-lock race.
        return bool(
            await session.scalar(select(has_references()).where(MediaObject.id == media_id))
        )

    async def purge_deleted_data(
        self, session: AsyncSession, *, limit: int, dry_run: bool
    ) -> tuple[int, int, int]:
        counts = []
        for table in (CustomerProject, UserFavorite, UserCommunityFavorite, PublicUserProfile):
            ids = list(
                await session.scalars(
                    select(table.id)
                    .join(User, User.id == table.user_id)
                    .where(User.status == UserStatus.DELETED.value)
                    .order_by(table.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True, of=table)
                )
            )
            if ids and not dry_run:
                await session.execute(delete(table).where(table.id.in_(ids)))
            counts.append(len(ids))
        return counts[0], counts[1] + counts[2], counts[3]
