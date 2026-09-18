from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import Product
from app.modules.crm.assortment_models import (
    CrmAccessory,
    CrmAccessoryCategory,
    CrmGarmentAccessoryRequirement,
    CrmGarmentFabricRequirement,
    CrmGarmentPackagingRule,
    CrmGarmentPattern,
    CrmPackagingBox,
)
from app.modules.crm.reference_models import CrmFabric, CrmGarmentModel, CrmGarmentSize
from app.modules.media.models import MediaObject, MediaStatus


class CrmAssortmentRepository:
    @staticmethod
    async def list_products(
        session: AsyncSession,
        *,
        model_id: int | None,
        category_id: int | None,
        active: bool | None,
    ) -> Sequence[Product]:
        statement = select(Product).options(selectinload(Product.variants))
        if model_id is not None:
            statement = statement.where(Product.garment_model_id == model_id)
        if category_id is not None:
            statement = statement.where(Product.category_id == category_id)
        if active is not None:
            statement = statement.where(Product.is_active.is_(active))
        return list(await session.scalars(statement.order_by(Product.id.desc())))

    @staticmethod
    async def add(session: AsyncSession, entity: object) -> None:
        session.add(entity)
        await session.flush()

    @staticmethod
    async def get_model(session: AsyncSession, model_id: int) -> CrmGarmentModel | None:
        return await session.get(CrmGarmentModel, model_id)

    @staticmethod
    async def get_size(session: AsyncSession, size_id: int) -> CrmGarmentSize | None:
        return await session.get(CrmGarmentSize, size_id)

    @staticmethod
    async def get_fabric(session: AsyncSession, fabric_id: int) -> CrmFabric | None:
        return await session.get(CrmFabric, fabric_id)

    @staticmethod
    async def get_ready_media(session: AsyncSession, media_id: int) -> MediaObject | None:
        return await session.scalar(
            select(MediaObject).where(
                MediaObject.id == media_id,
                MediaObject.status == MediaStatus.READY.value,
            )
        )

    @staticmethod
    async def list_patterns(
        session: AsyncSession,
        *,
        model_id: int | None,
        active: bool | None,
    ) -> Sequence[CrmGarmentPattern]:
        statement = select(CrmGarmentPattern)
        if model_id is not None:
            statement = statement.where(CrmGarmentPattern.garment_model_id == model_id)
        if active is not None:
            statement = statement.where(CrmGarmentPattern.is_active.is_(active))
        return list(await session.scalars(statement.order_by(CrmGarmentPattern.id.desc())))

    @staticmethod
    async def get_pattern_for_update(
        session: AsyncSession, pattern_id: int
    ) -> CrmGarmentPattern | None:
        return await session.scalar(
            select(CrmGarmentPattern).where(CrmGarmentPattern.id == pattern_id).with_for_update()
        )

    @staticmethod
    async def list_fabric_requirements(
        session: AsyncSession,
        *,
        model_id: int | None,
    ) -> Sequence[CrmGarmentFabricRequirement]:
        statement = select(CrmGarmentFabricRequirement)
        if model_id is not None:
            statement = statement.where(CrmGarmentFabricRequirement.garment_model_id == model_id)
        return list(
            await session.scalars(statement.order_by(CrmGarmentFabricRequirement.id.desc()))
        )

    @staticmethod
    async def get_fabric_requirement_for_update(
        session: AsyncSession, requirement_id: int
    ) -> CrmGarmentFabricRequirement | None:
        return await session.scalar(
            select(CrmGarmentFabricRequirement)
            .where(CrmGarmentFabricRequirement.id == requirement_id)
            .with_for_update()
        )

    @staticmethod
    async def get_primary_fabric_requirement(
        session: AsyncSession,
        *,
        model_id: int,
        exclude_id: int | None = None,
    ) -> CrmGarmentFabricRequirement | None:
        statement = select(CrmGarmentFabricRequirement).where(
            CrmGarmentFabricRequirement.garment_model_id == model_id,
            CrmGarmentFabricRequirement.is_primary.is_(True),
        )
        if exclude_id is not None:
            statement = statement.where(CrmGarmentFabricRequirement.id != exclude_id)
        return await session.scalar(statement)

    @staticmethod
    async def list_categories(
        session: AsyncSession, *, active: bool | None
    ) -> Sequence[CrmAccessoryCategory]:
        statement = select(CrmAccessoryCategory)
        if active is not None:
            statement = statement.where(CrmAccessoryCategory.is_active.is_(active))
        return list(await session.scalars(statement.order_by(CrmAccessoryCategory.name)))

    @staticmethod
    async def get_category(
        session: AsyncSession, category_id: int, *, lock: bool = False
    ) -> CrmAccessoryCategory | None:
        statement = select(CrmAccessoryCategory).where(CrmAccessoryCategory.id == category_id)
        return await session.scalar(statement.with_for_update() if lock else statement)

    @staticmethod
    async def list_accessories(
        session: AsyncSession,
        *,
        category_id: int | None,
        model_id: int | None,
        active: bool | None,
    ) -> Sequence[CrmAccessory]:
        statement = select(CrmAccessory).options(selectinload(CrmAccessory.model_requirements))
        if category_id is not None:
            statement = statement.where(CrmAccessory.category_id == category_id)
        if model_id is not None:
            statement = statement.join(CrmGarmentAccessoryRequirement).where(
                CrmGarmentAccessoryRequirement.garment_model_id == model_id
            )
        if active is not None:
            statement = statement.where(CrmAccessory.is_active.is_(active))
        return list(await session.scalars(statement.order_by(CrmAccessory.name)))

    @staticmethod
    async def get_accessory(
        session: AsyncSession, accessory_id: int, *, lock: bool = False
    ) -> CrmAccessory | None:
        statement = (
            select(CrmAccessory)
            .where(CrmAccessory.id == accessory_id)
            .options(selectinload(CrmAccessory.model_requirements))
        )
        return await session.scalar(statement.with_for_update() if lock else statement)

    @staticmethod
    async def list_accessory_requirements(
        session: AsyncSession,
        *,
        model_id: int | None,
    ) -> Sequence[CrmGarmentAccessoryRequirement]:
        statement = select(CrmGarmentAccessoryRequirement)
        if model_id is not None:
            statement = statement.where(CrmGarmentAccessoryRequirement.garment_model_id == model_id)
        return list(
            await session.scalars(statement.order_by(CrmGarmentAccessoryRequirement.id.desc()))
        )

    @staticmethod
    async def get_accessory_requirement_for_update(
        session: AsyncSession, requirement_id: int
    ) -> CrmGarmentAccessoryRequirement | None:
        return await session.scalar(
            select(CrmGarmentAccessoryRequirement)
            .where(CrmGarmentAccessoryRequirement.id == requirement_id)
            .with_for_update()
        )

    @staticmethod
    async def list_boxes(
        session: AsyncSession, *, active: bool | None
    ) -> Sequence[CrmPackagingBox]:
        statement = select(CrmPackagingBox)
        if active is not None:
            statement = statement.where(CrmPackagingBox.is_active.is_(active))
        return list(await session.scalars(statement.order_by(CrmPackagingBox.name)))

    @staticmethod
    async def get_box(
        session: AsyncSession, box_id: int, *, lock: bool = False
    ) -> CrmPackagingBox | None:
        statement = select(CrmPackagingBox).where(CrmPackagingBox.id == box_id)
        return await session.scalar(statement.with_for_update() if lock else statement)

    @staticmethod
    async def list_packaging_rules(
        session: AsyncSession,
        *,
        model_id: int | None,
    ) -> Sequence[CrmGarmentPackagingRule]:
        statement = select(CrmGarmentPackagingRule)
        if model_id is not None:
            statement = statement.where(CrmGarmentPackagingRule.garment_model_id == model_id)
        return list(
            await session.scalars(
                statement.order_by(
                    CrmGarmentPackagingRule.priority,
                    CrmGarmentPackagingRule.id,
                )
            )
        )

    @staticmethod
    async def get_packaging_rule_for_update(
        session: AsyncSession, rule_id: int
    ) -> CrmGarmentPackagingRule | None:
        return await session.scalar(
            select(CrmGarmentPackagingRule)
            .where(CrmGarmentPackagingRule.id == rule_id)
            .with_for_update()
        )
