from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.customer_projects.models import CustomerProject
from app.modules.customer_projects.repository import ProjectRepository
from app.modules.customer_projects.schemas import (
    ProjectCreate,
    ProjectDetail,
    ProjectPage,
    ProjectSnapshot,
    ProjectSummary,
    ProjectUpdate,
)
from app.modules.identity.customer_writes import lock_active_customer
from app.modules.identity.security import ensure_utc


class ProjectNotFoundError(Exception):
    pass


class ProjectConflictError(Exception):
    pass


class ProjectGoneError(Exception):
    pass


class ProjectMediaError(Exception):
    pass


class ProjectService:
    def __init__(self, settings: Settings, repository: ProjectRepository | None = None) -> None:
        self.repository = repository or ProjectRepository()
        self.private_bucket = settings.minio_customer_projects_bucket

    async def create(
        self, session: AsyncSession, *, user_id: int, payload: ProjectCreate
    ) -> tuple[ProjectDetail, bool]:
        if not await lock_active_customer(session, user_id):
            raise ProjectNotFoundError
        encoded = json.dumps(
            payload.model_dump(mode="json", by_alias=True, exclude_unset=True),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        existing = await self.repository.get_by_key(
            session, user_id=user_id, client_key=payload.client_key
        )
        if existing is not None:
            return self.replay(existing, digest), False
        if not await self.repository.product_is_available(session, product_id=payload.product_id):
            raise ProjectNotFoundError
        values = {
            "client_key": payload.client_key,
            "creation_sha256": digest,
            "product_id": payload.product_id,
            "kind": payload.kind,
            "title": payload.title,
            "snapshot": payload.snapshot.model_dump(mode="json", by_alias=True, exclude_unset=True),
        }
        record, created = await self.repository.create_once(session, user_id=user_id, values=values)
        if not created:
            return self.replay(record, digest), False
        await self.validate_media(session, record=record, snapshot=payload.snapshot, retained=False)
        await self.repository.replace_media(
            session, project_id=record.id, media_ids=payload.snapshot.media_ids()
        )
        return self.detail(record), True

    def replay(self, record: CustomerProject, digest: str) -> ProjectDetail:
        if record.creation_sha256 != digest:
            raise ProjectConflictError
        if record.deleted_at is not None:
            raise ProjectGoneError
        return self.detail(record)

    async def get(self, session: AsyncSession, *, user_id: int, project_id: int) -> ProjectDetail:
        record = await self.repository.get_owned(session, user_id=user_id, project_id=project_id)
        if record is None or record.deleted_at is not None:
            raise ProjectNotFoundError
        return self.detail(record)

    async def creation_receipt(
        self, session: AsyncSession, *, user_id: int, client_key: str
    ) -> ProjectSummary:
        record = await self.repository.creation_receipt(
            session, user_id=user_id, client_key=client_key
        )
        if record is None:
            raise ProjectNotFoundError
        if record["deleted_at"] is not None:
            raise ProjectGoneError
        return self.summary(dict(record))

    async def update(
        self, session: AsyncSession, *, user_id: int, project_id: int, payload: ProjectUpdate
    ) -> ProjectDetail:
        if not await lock_active_customer(session, user_id):
            raise ProjectNotFoundError
        record = await self.repository.get_owned(session, user_id=user_id, project_id=project_id)
        if record is None or record.deleted_at is not None:
            raise ProjectNotFoundError
        if record.version != payload.expected_version:
            raise ProjectConflictError
        await self.validate_media(session, record=record, snapshot=payload.snapshot, retained=True)
        updated = await self.repository.update_version(
            session,
            user_id=user_id,
            project_id=project_id,
            expected_version=payload.expected_version,
            values={
                "kind": payload.kind,
                "title": payload.title,
                "snapshot": payload.snapshot.model_dump(
                    mode="json", by_alias=True, exclude_unset=True
                ),
            },
        )
        if updated is None:
            raise ProjectConflictError
        await self.repository.replace_media(
            session, project_id=project_id, media_ids=payload.snapshot.media_ids()
        )
        return self.detail(updated)

    async def remove(
        self, session: AsyncSession, *, user_id: int, project_id: int, expected_version: int
    ) -> None:
        if not await lock_active_customer(session, user_id):
            raise ProjectNotFoundError
        record = await self.repository.get_owned(session, user_id=user_id, project_id=project_id)
        if record is None:
            raise ProjectNotFoundError
        if record.deleted_at is not None:
            if record.version == expected_version + 1:
                return
            raise ProjectConflictError
        deleted = await self.repository.update_version(
            session,
            user_id=user_id,
            project_id=project_id,
            expected_version=expected_version,
            values={"deleted_at": datetime.now(timezone.utc), "snapshot": None},
        )
        if deleted is None:
            raise ProjectConflictError
        await self.repository.replace_media(session, project_id=project_id, media_ids=set())

    async def list_page(
        self, session: AsyncSession, *, user_id: int, kind: str, cursor: int | None, limit: int
    ) -> ProjectPage:
        records = await self.repository.list_page(
            session, user_id=user_id, kind=kind, cursor=cursor, limit=limit + 1
        )
        page = records[:limit]
        return ProjectPage(
            items=[self.summary(dict(record)) for record in page],
            next_cursor=page[-1]["id"] if len(records) > limit else None,
        )

    async def validate_media(
        self,
        session: AsyncSession,
        *,
        record: CustomerProject,
        snapshot: ProjectSnapshot,
        retained: bool,
    ) -> None:
        requested = snapshot.media_ids()
        allowed = await self.repository.allowed_media_ids(
            session,
            user_id=record.user_id,
            product_id=record.product_id,
            media_ids=requested,
            private_bucket=self.private_bucket,
            project_id=record.id if retained else None,
        )
        if allowed != requested:
            raise ProjectMediaError

    @staticmethod
    def summary(values: dict[str, Any]) -> ProjectSummary:
        return ProjectSummary(
            **{
                **values,
                "created_at": ensure_utc(values["created_at"]),
                "updated_at": ensure_utc(values["updated_at"]),
            }
        )

    def detail(self, record: CustomerProject) -> ProjectDetail:
        summary = self.summary({key: getattr(record, key) for key in ProjectSummary.model_fields})
        return ProjectDetail(
            **summary.model_dump(), snapshot=ProjectSnapshot.model_validate(record.snapshot)
        )
