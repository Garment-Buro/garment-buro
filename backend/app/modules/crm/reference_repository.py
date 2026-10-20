from __future__ import annotations

from datetime import datetime

from sqlalchemy import column, select, values
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload, selectinload

from app.modules.catalog.models import Product
from app.modules.crm.reference_models import (
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentModelCategory,
    CrmGarmentSize,
    CrmReferenceEvent,
    CrmTechCard,
    CrmTechCardRevision,
)
from app.modules.crm.reference_schemas import GARMENT_MODEL_SIZE_LIMIT
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
            .options(raiseload(CrmGarmentModel.sizes))
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    @staticmethod
    async def active_garment_sizes(
        session: AsyncSession, *, garment_model_id: int
    ) -> list[CrmGarmentSize]:
        return list(
            await session.scalars(
                select(CrmGarmentSize)
                .where(
                    CrmGarmentSize.garment_model_id == garment_model_id,
                    CrmGarmentSize.is_active.is_(True),
                )
                .order_by(CrmGarmentSize.sort_order, CrmGarmentSize.id)
                .limit(GARMENT_MODEL_SIZE_LIMIT + 1)
                .execution_options(populate_existing=True)
            )
        )

    @staticmethod
    async def garment_sizes_by_codes(
        session: AsyncSession, *, garment_model_id: int, codes: set[str]
    ) -> list[CrmGarmentSize]:
        if not codes:
            return []
        requested = (
            values(column("code", CrmGarmentSize.code.type))
            .data([(code,) for code in sorted(codes)])
            .cte("requested_size_codes")
        )
        # A direct IN over common codes can scan the entire history. Keep one
        # unique-key probe per requested code, then hydrate only those primary IDs.
        matched_id = (
            select(CrmGarmentSize.id)
            .where(
                CrmGarmentSize.garment_model_id == garment_model_id,
                CrmGarmentSize.code == requested.c.code,
            )
            .limit(1)
            .correlate(requested)
            .scalar_subquery()
        )
        # PostgreSQL otherwise may repeat a scalar probe during ID deduplication.
        matched = (
            select(matched_id.label("id"))
            .select_from(requested)
            .cte("matched_size_ids")
            .prefix_with("MATERIALIZED", dialect="postgresql")
        )
        return list(
            await session.scalars(
                select(CrmGarmentSize)
                .where(CrmGarmentSize.id.in_(select(matched.c.id)))
                .execution_options(populate_existing=True)
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
            .execution_options(populate_existing=True)
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

    @staticmethod
    async def garment_model_category_codes_starting_with(
        session: AsyncSession,
        *,
        prefix: str,
    ) -> set[str]:
        return set(
            await session.scalars(
                select(CrmGarmentModelCategory.code).where(
                    CrmGarmentModelCategory.code.startswith(prefix)
                )
            )
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
            select(Product)
            .where(Product.id == catalog_product_id)
            .with_for_update()
            .execution_options(populate_existing=True)
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
            .with_for_update()
            .execution_options(populate_existing=True)
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
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def find_tech_card_revision(
        self,
        session: AsyncSession,
        *,
        tech_card_id: int,
        revision_number: int | None = None,
        status: str | None = None,
        checkpoints: bool = False,
    ) -> CrmTechCardRevision | None:
        statement = select(CrmTechCardRevision).where(
            CrmTechCardRevision.tech_card_id == tech_card_id
        )
        if revision_number is not None:
            statement = statement.where(CrmTechCardRevision.revision_number == revision_number)
        if status is not None:
            statement = statement.where(CrmTechCardRevision.status == status)
        if checkpoints:
            statement = statement.options(selectinload(CrmTechCardRevision.checkpoints))
        return await session.scalar(statement.limit(1).execution_options(populate_existing=True))

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
