from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import Product
from app.modules.crm.reference_models import (
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentModelCategory,
    CrmReferenceEvent,
    CrmTechCard,
    CrmTechCardRevision,
)
from app.modules.media.models import MediaObject, MediaStatus


class CrmReferenceRepository:
    @staticmethod
    async def add(session: AsyncSession, entity: object) -> None:
        session.add(entity)
        await session.flush()

    async def get_fabric_for_update(
        self,
        session: AsyncSession,
        *,
        fabric_id: int,
    ) -> CrmFabric | None:
        return await session.scalar(
            select(CrmFabric).where(CrmFabric.id == fabric_id).with_for_update()
        )

    async def get_garment_model_for_update(
        self,
        session: AsyncSession,
        *,
        garment_model_id: int,
    ) -> CrmGarmentModel | None:
        return await session.scalar(
            select(CrmGarmentModel)
            .where(CrmGarmentModel.id == garment_model_id)
            .options(selectinload(CrmGarmentModel.sizes))
            .with_for_update()
        )

    @staticmethod
    async def list_garment_model_categories(
        session: AsyncSession,
    ) -> list[CrmGarmentModelCategory]:
        return list(
            await session.scalars(
                select(CrmGarmentModelCategory).order_by(CrmGarmentModelCategory.id.asc())
            )
        )

    async def get_garment_model_category_for_update(
        self,
        session: AsyncSession,
        *,
        category_id: int,
    ) -> CrmGarmentModelCategory | None:
        return await session.scalar(
            select(CrmGarmentModelCategory)
            .where(CrmGarmentModelCategory.id == category_id)
            .with_for_update()
        )

    @staticmethod
    async def active_garment_model_category_exists(
        session: AsyncSession,
        *,
        category_id: int,
    ) -> bool:
        return (
            await session.scalar(
                select(CrmGarmentModelCategory.id).where(
                    CrmGarmentModelCategory.id == category_id,
                    CrmGarmentModelCategory.is_active.is_(True),
                )
            )
            is not None
        )

    async def public_ready_media_exists(
        self,
        session: AsyncSession,
        *,
        media_object_id: int,
    ) -> bool:
        return (
            await session.scalar(
                select(MediaObject.id).where(
                    MediaObject.id == media_object_id,
                    MediaObject.status == MediaStatus.READY.value,
                    MediaObject.is_public.is_(True),
                )
            )
            is not None
        )

    async def get_catalog_product_for_update(
        self,
        session: AsyncSession,
        *,
        catalog_product_id: int,
    ) -> Product | None:
        return await session.scalar(
            select(Product).where(Product.id == catalog_product_id).with_for_update()
        )

    async def get_tech_card_for_update(
        self,
        session: AsyncSession,
        *,
        tech_card_id: int,
    ) -> CrmTechCard | None:
        return await session.scalar(
            select(CrmTechCard)
            .where(CrmTechCard.id == tech_card_id)
            .options(
                selectinload(CrmTechCard.revisions).selectinload(CrmTechCardRevision.checkpoints)
            )
            .with_for_update()
        )

    async def get_tech_card_by_model_for_update(
        self,
        session: AsyncSession,
        *,
        garment_model_id: int,
    ) -> CrmTechCard | None:
        return await session.scalar(
            select(CrmTechCard)
            .where(CrmTechCard.garment_model_id == garment_model_id)
            .options(selectinload(CrmTechCard.revisions))
            .with_for_update()
        )

    async def list_tech_cards(
        self,
        session: AsyncSession,
        *,
        garment_model_id: int | None = None,
    ) -> list[CrmTechCard]:
        statement = select(CrmTechCard).options(
            selectinload(CrmTechCard.revisions).selectinload(CrmTechCardRevision.checkpoints)
        )
        if garment_model_id is not None:
            statement = statement.where(CrmTechCard.garment_model_id == garment_model_id)
        return list(await session.scalars(statement.order_by(CrmTechCard.id.desc())))

    @staticmethod
    async def add_event(
        session: AsyncSession,
        *,
        entity_type: str,
        entity_id: int,
        entity_version: int,
        action: str,
        actor_user_id: int | None,
        snapshot_sha256: str,
        details: dict[str, object],
        occurred_at: datetime,
    ) -> None:
        session.add(
            CrmReferenceEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                entity_version=entity_version,
                action=action,
                actor_user_id=actor_user_id,
                snapshot_sha256=snapshot_sha256,
                details=details,
                occurred_at=occurred_at,
            )
        )
        await session.flush()
