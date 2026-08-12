from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.material_models import CrmMaterialBalance
from app.modules.crm.models import CrmOrderProject, CrmProductionUnit
from app.modules.crm.production_models import (
    CrmProductionPlanRevision,
    CrmProductionPlanStatus,
)
from app.modules.crm.reference_models import (
    CrmCatalogProductModelLink,
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentSize,
    CrmTechCard,
    CrmTechCardRevision,
    CrmTechCardRevisionStatus,
)
from app.modules.orders.models import OrderItem


@dataclass(frozen=True, slots=True)
class CrmUnitEvidence:
    unit: CrmProductionUnit
    order_item: OrderItem | None
    active_plan: CrmProductionPlanRevision | None


@dataclass(frozen=True, slots=True)
class CrmPublishedTechCard:
    card: CrmTechCard
    revision: CrmTechCardRevision


class CrmReadRepository:
    async def list_projects(
        self,
        session: AsyncSession,
        *,
        status: str | None,
        assigned_to_user_id: int | None,
        cursor: int | None,
        limit: int,
    ) -> tuple[list[CrmOrderProject], int | None]:
        statement = select(CrmOrderProject)
        if status is not None:
            statement = statement.where(CrmOrderProject.status == status)
        if assigned_to_user_id is not None:
            statement = statement.where(CrmOrderProject.assigned_to_user_id == assigned_to_user_id)
        if cursor is not None:
            statement = statement.where(CrmOrderProject.id < cursor)
        projects = list(
            await session.scalars(statement.order_by(CrmOrderProject.id.desc()).limit(limit + 1))
        )
        has_more = len(projects) > limit
        page = projects[:limit]
        next_cursor = page[-1].id if has_more and page else None
        return page, next_cursor

    @staticmethod
    async def get_project(
        session: AsyncSession,
        *,
        project_id: int,
    ) -> CrmOrderProject | None:
        return await session.get(CrmOrderProject, project_id)

    @staticmethod
    async def list_project_units(
        session: AsyncSession,
        *,
        project_id: int,
        cursor: int | None,
        limit: int,
    ) -> tuple[list[CrmUnitEvidence], int | None]:
        statement = (
            select(CrmProductionUnit, OrderItem, CrmProductionPlanRevision)
            .outerjoin(OrderItem, OrderItem.id == CrmProductionUnit.order_item_id)
            .outerjoin(
                CrmProductionPlanRevision,
                and_(
                    CrmProductionPlanRevision.production_unit_id == CrmProductionUnit.id,
                    CrmProductionPlanRevision.status == CrmProductionPlanStatus.ACTIVE.value,
                ),
            )
            .where(CrmProductionUnit.project_id == project_id)
        )
        if cursor is not None:
            statement = statement.where(CrmProductionUnit.id > cursor)
        rows = list(
            await session.execute(statement.order_by(CrmProductionUnit.id).limit(limit + 1))
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = page[-1][0].id if has_more and page else None
        return [CrmUnitEvidence(unit, item, plan) for unit, item, plan in page], next_cursor

    @staticmethod
    async def count_project_units(
        session: AsyncSession,
        *,
        project_id: int,
    ) -> int:
        return int(
            await session.scalar(
                select(func.count(CrmProductionUnit.id)).where(
                    CrmProductionUnit.project_id == project_id
                )
            )
            or 0
        )

    @staticmethod
    async def list_fabrics(
        session: AsyncSession,
        *,
        is_active: bool | None,
        cursor: int | None,
        limit: int,
    ) -> tuple[list[tuple[CrmFabric, CrmMaterialBalance | None]], int | None]:
        statement = select(CrmFabric, CrmMaterialBalance).outerjoin(
            CrmMaterialBalance,
            CrmMaterialBalance.fabric_id == CrmFabric.id,
        )
        if is_active is not None:
            statement = statement.where(CrmFabric.is_active.is_(is_active))
        if cursor is not None:
            statement = statement.where(CrmFabric.id < cursor)
        rows = list(await session.execute(statement.order_by(CrmFabric.id.desc()).limit(limit + 1)))
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = page[-1][0].id if has_more and page else None
        return [(row[0], row[1]) for row in page], next_cursor

    @staticmethod
    async def list_garment_models(
        session: AsyncSession,
        *,
        is_active: bool | None,
        cursor: int | None,
        limit: int,
    ) -> tuple[list[CrmGarmentModel], int | None]:
        statement = select(CrmGarmentModel)
        if is_active is not None:
            statement = statement.where(CrmGarmentModel.is_active.is_(is_active))
        if cursor is not None:
            statement = statement.where(CrmGarmentModel.id < cursor)
        models = list(
            await session.scalars(statement.order_by(CrmGarmentModel.id.desc()).limit(limit + 1))
        )
        has_more = len(models) > limit
        page = models[:limit]
        next_cursor = page[-1].id if has_more and page else None
        return page, next_cursor

    @staticmethod
    async def list_sizes_by_model(
        session: AsyncSession,
        *,
        garment_model_ids: list[int],
    ) -> dict[int, list[CrmGarmentSize]]:
        if not garment_model_ids:
            return {}
        sizes: dict[int, list[CrmGarmentSize]] = {}
        for size in await session.scalars(
            select(CrmGarmentSize)
            .where(CrmGarmentSize.garment_model_id.in_(garment_model_ids))
            .order_by(
                CrmGarmentSize.garment_model_id,
                CrmGarmentSize.sort_order,
                CrmGarmentSize.id,
            )
        ):
            sizes.setdefault(size.garment_model_id, []).append(size)
        return sizes

    @staticmethod
    async def list_catalog_products_by_model(
        session: AsyncSession,
        *,
        garment_model_ids: list[int],
    ) -> dict[int, list[int]]:
        if not garment_model_ids:
            return {}
        products: dict[int, list[int]] = {}
        rows = await session.execute(
            select(
                CrmCatalogProductModelLink.garment_model_id,
                CrmCatalogProductModelLink.catalog_product_id,
            )
            .where(CrmCatalogProductModelLink.garment_model_id.in_(garment_model_ids))
            .order_by(
                CrmCatalogProductModelLink.garment_model_id,
                CrmCatalogProductModelLink.catalog_product_id,
            )
        )
        for model_id, product_id in rows:
            products.setdefault(model_id, []).append(product_id)
        return products

    @staticmethod
    async def list_published_cards_by_model(
        session: AsyncSession,
        *,
        garment_model_ids: list[int],
    ) -> dict[int, CrmPublishedTechCard]:
        if not garment_model_ids:
            return {}
        rows = await session.execute(
            select(CrmTechCard, CrmTechCardRevision)
            .join(
                CrmTechCardRevision,
                and_(
                    CrmTechCardRevision.tech_card_id == CrmTechCard.id,
                    CrmTechCardRevision.status == CrmTechCardRevisionStatus.PUBLISHED.value,
                ),
            )
            .where(CrmTechCard.garment_model_id.in_(garment_model_ids))
        )
        return {
            card.garment_model_id: CrmPublishedTechCard(card, revision) for card, revision in rows
        }
