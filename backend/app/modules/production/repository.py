from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import CrmOrderProject, CrmProductionUnit
from app.modules.production.models import (
    ProductionBag,
    ProductionEvent,
    ProductionSpecification,
    ProductionWorkItem,
)


class ProductionRepository:
    async def project(self, session: AsyncSession, project_id: int, *, lock=False):
        query = select(CrmOrderProject).where(CrmOrderProject.id == project_id)
        if lock:
            query = query.with_for_update()
        return await session.scalar(query.execution_options(populate_existing=True))

    async def bag(self, session, project_id):
        return await session.scalar(
            select(ProductionBag)
            .where(ProductionBag.project_id == project_id)
            .execution_options(populate_existing=True)
        )

    async def units(self, session, project_id):
        return list(
            await session.scalars(
                select(CrmProductionUnit)
                .where(CrmProductionUnit.project_id == project_id)
                .order_by(CrmProductionUnit.id)
            )
        )

    async def work(self, session, bag_id):
        return list(
            await session.scalars(
                select(ProductionWorkItem)
                .where(ProductionWorkItem.bag_id == bag_id)
                .order_by(ProductionWorkItem.unit_id)
            )
        )

    async def specifications(self, session, work):
        ids = [x.specification_id for x in work if x.specification_id]
        return {
            x.id: x
            for x in await session.scalars(
                select(ProductionSpecification).where(ProductionSpecification.id.in_(ids))
            )
        }

    async def event(self, session, key):
        return await session.scalar(
            select(ProductionEvent).where(ProductionEvent.command_key == key)
        )
