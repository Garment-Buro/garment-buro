from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import Product
from app.modules.crm.reference_models import (
    CrmCatalogProductModelLink,
    CrmFabric,
    CrmGarmentModel,
    CrmReferenceEvent,
    CrmTechCard,
    CrmTechCardRevision,
)


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

    async def catalog_product_exists(
        self,
        session: AsyncSession,
        *,
        catalog_product_id: int,
    ) -> bool:
        return (
            await session.scalar(select(Product.id).where(Product.id == catalog_product_id))
            is not None
        )

    async def get_catalog_link_for_update(
        self,
        session: AsyncSession,
        *,
        catalog_product_id: int,
    ) -> CrmCatalogProductModelLink | None:
        return await session.scalar(
            select(CrmCatalogProductModelLink)
            .where(CrmCatalogProductModelLink.catalog_product_id == catalog_product_id)
            .with_for_update()
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
