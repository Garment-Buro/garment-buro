from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.crm.file_models import CrmFileAccessEvent, CrmFileAttachment
from app.modules.crm.models import CrmOrderProject, CrmProductionUnit
from app.modules.crm.reference_models import CrmTechCardRevision
from app.modules.media.models import MediaObject, MediaStatus


class CrmFileRepository:
    async def target_exists(
        self,
        session: AsyncSession,
        *,
        tech_card_revision_id: int | None,
        production_project_id: int | None,
        production_unit_id: int | None,
    ) -> bool:
        if tech_card_revision_id is not None:
            return await session.get(CrmTechCardRevision, tech_card_revision_id) is not None
        if production_project_id is not None:
            return await session.get(CrmOrderProject, production_project_id) is not None
        if production_unit_id is not None:
            return await session.get(CrmProductionUnit, production_unit_id) is not None
        return False

    async def add_attachment(
        self,
        session: AsyncSession,
        attachment: CrmFileAttachment,
    ) -> None:
        session.add(attachment)
        await session.flush()

    async def get_attachment_for_slot(
        self,
        session: AsyncSession,
        *,
        role: str,
        tech_card_revision_id: int | None,
        production_project_id: int | None,
        production_unit_id: int | None,
        sort_order: int,
    ) -> CrmFileAttachment | None:
        return await session.scalar(
            select(CrmFileAttachment)
            .where(
                CrmFileAttachment.role == role,
                CrmFileAttachment.tech_card_revision_id == tech_card_revision_id,
                CrmFileAttachment.production_project_id == production_project_id,
                CrmFileAttachment.production_unit_id == production_unit_id,
                CrmFileAttachment.sort_order == sort_order,
            )
            .options(selectinload(CrmFileAttachment.media))
        )

    async def get_ready_attachment(
        self,
        session: AsyncSession,
        *,
        attachment_id: int,
    ) -> CrmFileAttachment | None:
        return await session.scalar(
            select(CrmFileAttachment)
            .where(CrmFileAttachment.id == attachment_id)
            .options(selectinload(CrmFileAttachment.media))
            .join(MediaObject, MediaObject.id == CrmFileAttachment.media_object_id)
            .where(MediaObject.status == MediaStatus.READY.value)
        )

    @staticmethod
    async def add_access_event(
        session: AsyncSession,
        event: CrmFileAccessEvent,
    ) -> None:
        session.add(event)
        await session.flush()
