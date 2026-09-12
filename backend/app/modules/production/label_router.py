"""Possession of a random label grants only a minimal, read-only garment manifest."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.crm.models import CrmOrderProject, CrmProductionUnit
from app.modules.orders.models import OrderItem
from app.modules.production.models import ProductionBag, ProductionWorkItem

router = APIRouter()


@router.get("/labels/{token}")
async def label(
    token: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{43}$")],
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    if not request.app.state.settings.production_terminal_enabled:
        raise HTTPException(503, "Терминал выключен")
    bag = await session.scalar(select(ProductionBag).where(ProductionBag.public_token == token))
    item = None
    if bag is None:
        item = await session.scalar(
            select(ProductionWorkItem).where(ProductionWorkItem.public_token == token)
        )
        bag = await session.get(ProductionBag, item.bag_id) if item else None
    if bag is None:
        raise HTTPException(404, "Мешок не найден")
    project = await session.get(CrmOrderProject, bag.project_id)
    query = (
        select(ProductionWorkItem, CrmProductionUnit, OrderItem)
        .join(CrmProductionUnit, CrmProductionUnit.id == ProductionWorkItem.unit_id)
        .join(OrderItem, OrderItem.id == CrmProductionUnit.order_item_id)
        .where(ProductionWorkItem.bag_id == bag.id)
    )
    if item:
        query = query.where(ProductionWorkItem.id == item.id)
    rows = (await session.execute(query.order_by(CrmProductionUnit.unit_number))).all()
    return {
        "project_id": project.id,
        "order_id": project.order_id,
        "unit_id": item.unit_id if item else None,
        "state": bag.state,
        "units": [
            {
                "id": unit.id,
                "number": unit.unit_number,
                "title": source.title_snapshot,
                "size": source.size_snapshot,
                "color": source.color_snapshot,
                "state": work.lane or bag.state,
            }
            for work, unit, source in rows
        ],
    }
