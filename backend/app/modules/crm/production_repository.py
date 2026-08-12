from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.material_models import CrmMaterialReservation
from app.modules.crm.models import CrmProductionUnit
from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.crm.reference_models import (
    CrmCatalogProductModelLink,
    CrmGarmentSize,
    CrmTechCard,
    CrmTechCardRevision,
)
from app.modules.orders.models import OrderItem


class CrmProductionRepository:
    async def get_unit_for_update(
        self,
        session: AsyncSession,
        *,
        production_unit_id: int,
    ) -> CrmProductionUnit | None:
        return await session.scalar(
            select(CrmProductionUnit)
            .where(CrmProductionUnit.id == production_unit_id)
            .with_for_update()
        )

    async def get_order_item(
        self,
        session: AsyncSession,
        *,
        order_item_id: int,
    ) -> OrderItem | None:
        return await session.get(OrderItem, order_item_id)

    async def get_catalog_model_link(
        self,
        session: AsyncSession,
        *,
        catalog_product_id: int,
    ) -> CrmCatalogProductModelLink | None:
        return await session.scalar(
            select(CrmCatalogProductModelLink).where(
                CrmCatalogProductModelLink.catalog_product_id == catalog_product_id
            )
        )

    async def list_active_sizes(
        self,
        session: AsyncSession,
        *,
        garment_model_id: int,
    ) -> list[CrmGarmentSize]:
        return list(
            await session.scalars(
                select(CrmGarmentSize)
                .where(
                    CrmGarmentSize.garment_model_id == garment_model_id,
                    CrmGarmentSize.is_active.is_(True),
                )
                .order_by(CrmGarmentSize.sort_order, CrmGarmentSize.id)
            )
        )

    async def get_published_revision(
        self,
        session: AsyncSession,
        *,
        tech_card_revision_id: int,
    ) -> tuple[CrmTechCardRevision, CrmTechCard] | None:
        row = (
            await session.execute(
                select(CrmTechCardRevision, CrmTechCard)
                .join(CrmTechCard, CrmTechCard.id == CrmTechCardRevision.tech_card_id)
                .where(
                    CrmTechCardRevision.id == tech_card_revision_id,
                    CrmTechCardRevision.status == "published",
                    CrmTechCard.is_active.is_(True),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    async def list_plan_revisions_for_update(
        self,
        session: AsyncSession,
        *,
        production_unit_id: int,
    ) -> list[CrmProductionPlanRevision]:
        return list(
            await session.scalars(
                select(CrmProductionPlanRevision)
                .where(CrmProductionPlanRevision.production_unit_id == production_unit_id)
                .order_by(CrmProductionPlanRevision.revision_number)
                .with_for_update()
            )
        )

    async def has_active_material_reservations(
        self,
        session: AsyncSession,
        *,
        plan_revision_id: int,
    ) -> bool:
        return (
            await session.scalar(
                select(CrmMaterialReservation.id)
                .where(
                    CrmMaterialReservation.production_plan_revision_id == plan_revision_id,
                    CrmMaterialReservation.status == "active",
                )
                .limit(1)
            )
            is not None
        )
