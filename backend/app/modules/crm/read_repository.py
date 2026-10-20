from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import CrmOrderProject, CrmProductionUnit
from app.modules.crm.production_models import (
    CrmProductionPlanRevision,
    CrmProductionPlanStatus,
)
from app.modules.orders.models import OrderItem


@dataclass(frozen=True, slots=True)
class CrmUnitEvidence:
    unit: CrmProductionUnit
    order_item: OrderItem | None
    active_plan: CrmProductionPlanRevision | None


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
        # The legacy CRM contract represents paid orders only; demos live in the terminal.
        statement = select(CrmOrderProject).where(CrmOrderProject.is_demo.is_(False))
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
        return await session.scalar(
            select(CrmOrderProject).where(
                CrmOrderProject.id == project_id, CrmOrderProject.is_demo.is_(False)
            )
        )

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
