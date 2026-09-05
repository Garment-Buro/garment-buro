from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.delivery.directory import DIRECTORY_KEY, search_statement
from app.modules.delivery.directory_models import PickupDirectoryState

router = APIRouter(prefix="/api/cdek", tags=["delivery"])


@router.get("/points")
async def list_pickup_points(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    q: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    state = await session.get(PickupDirectoryState, DIRECTORY_KEY)
    if state is None or state.updated_at is None:
        raise HTTPException(
            503,
            "Справочник СДЭК ещё не загружен. Попробуйте позже.",
            headers={"Retry-After": "60", "Cache-Control": "no-store"},
        )
    updated_at = state.updated_at.replace(tzinfo=UTC)
    # Very old points must not appear selectable after a prolonged outage.
    if datetime.now(UTC) - updated_at > timedelta(days=7):
        raise HTTPException(503, "Справочник СДЭК требует обновления.")
    statement = search_statement(q)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    points = await session.scalars(statement.offset(offset).limit(limit))
    response.headers["Cache-Control"] = "public, max-age=300"
    return {
        "points": [point.payload for point in points],
        "total": total,
        "updated_at": updated_at,
        "stale": datetime.now(UTC) - updated_at > timedelta(days=1),
    }
