from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.crm.directory_api import read_reference_page
from app.modules.crm.pattern_directory_schemas import (
    PatternContext,
    PatternCoverage,
    PatternFilePage,
    PatternFileQuery,
    PatternGridQuery,
    PatternModelPage,
    PatternModelQuery,
    PatternSizePage,
    PatternSizeQuery,
)
from app.modules.crm.pattern_directory_service import PatternDirectoryService, PatternGridChanged

Session = Annotated[AsyncSession, Depends(get_database_session)]
Identity = Annotated[int, Path(gt=0, le=2_147_483_647)]


def pattern_directory_router(authorize):
    router = APIRouter(dependencies=[Depends(authorize)])

    @router.get("/directory/pattern-models", response_model=PatternModelPage)
    async def models(
        response: Response, session: Session, query: Annotated[PatternModelQuery, Query()]
    ):
        return await read_reference_page(
            response, PatternDirectoryService().page(session, "pattern-models", query)
        )

    @router.get("/directory/patterns", response_model=PatternFilePage)
    async def files(
        response: Response, session: Session, query: Annotated[PatternFileQuery, Query()]
    ):
        return await read_reference_page(
            response, PatternDirectoryService().page(session, "patterns", query)
        )

    @router.get("/directory/pattern-sizes", response_model=PatternSizePage)
    async def sizes(
        response: Response, session: Session, query: Annotated[PatternSizeQuery, Query()]
    ):
        return await read_reference_page(
            response, PatternDirectoryService().page(session, "pattern-sizes", query)
        )

    @router.get("/models/{model_id}/pattern-coverage", response_model=PatternCoverage)
    async def coverage(
        response: Response,
        session: Session,
        model_id: Identity,
        query: Annotated[PatternGridQuery, Query()],
    ):
        response.headers["Cache-Control"] = "no-store"
        try:
            return required(await PatternDirectoryService().coverage(session, model_id, query))
        except PatternGridChanged as error:
            raise HTTPException(
                409,
                detail={"code": "pattern_grid_changed", "message": str(error)},
                headers={"Cache-Control": "no-store"},
            ) from error
        except ValueError as error:
            raise HTTPException(
                422,
                detail={"code": "pattern_grid_page_out_of_range", "message": str(error)},
                headers={"Cache-Control": "no-store"},
            ) from error

    @router.get("/models/{model_id}/pattern-size/{size_id}", response_model=PatternContext)
    async def context(response: Response, session: Session, model_id: Identity, size_id: Identity):
        response.headers["Cache-Control"] = "no-store"
        return required(await PatternDirectoryService().context(session, model_id, size_id))

    @router.get("/patterns/{pattern_id}", response_model=PatternContext)
    async def editor(response: Response, session: Session, pattern_id: Identity):
        response.headers["Cache-Control"] = "no-store"
        return required(await PatternDirectoryService().editor(session, pattern_id))

    return router


def required(row):
    if row is None:
        raise HTTPException(
            404, "Модель, размер или лекало не найдены", headers={"Cache-Control": "no-store"}
        )
    return row
