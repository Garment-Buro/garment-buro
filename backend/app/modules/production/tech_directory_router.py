from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.crm.directory_api import read_reference_page
from app.modules.crm.tech_directory_schemas import (
    TechCardDirectoryQuery,
    TechCardEditorSource,
    TechCardModelPage,
    TechCardModelQuery,
    TechCardPage,
)
from app.modules.crm.tech_directory_service import TechDirectoryService

Session = Annotated[AsyncSession, Depends(get_database_session)]


def tech_directory_router(authorize):
    router = APIRouter(dependencies=[Depends(authorize)])

    @router.get("/directory/tech-cards", response_model=TechCardPage)
    async def cards(
        response: Response, session: Session, query: Annotated[TechCardDirectoryQuery, Query()]
    ):
        return await read_reference_page(
            response, TechDirectoryService().page(session, "tech-cards", query)
        )

    @router.get("/directory/tech-card-models", response_model=TechCardModelPage)
    async def models(
        response: Response, session: Session, query: Annotated[TechCardModelQuery, Query()]
    ):
        return await read_reference_page(
            response, TechDirectoryService().page(session, "tech-card-models", query)
        )

    @router.get("/tech-cards/{card_id}/revision-source", response_model=TechCardEditorSource)
    async def source(
        response: Response,
        session: Session,
        card_id: Annotated[int, Path(gt=0, le=2_147_483_647)],
    ):
        response.headers["Cache-Control"] = "no-store"
        row = await TechDirectoryService().editor(session, card_id)
        if row is None:
            raise HTTPException(404, "Техкарта не найдена", headers={"Cache-Control": "no-store"})
        if row.draft_revision_number is not None:
            raise HTTPException(
                409,
                "У техкарты уже есть черновик. Сначала опубликуйте или отклоните его.",
                headers={"Cache-Control": "no-store"},
            )
        return row

    return router
