"""Bounded catalog editor references, independent of the login surface."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.catalog.editor_option_repository import EditorOptionRepository
from app.modules.catalog.editor_option_schemas import (
    EditorModel,
    EditorOptionsQuery,
    EditorSizeQuery,
    FabricOption,
    FabricOptionsPage,
    ModelOption,
    ModelOptionsPage,
    SelectedFabricQuery,
    SelectedSizeQuery,
    SizeOption,
    SizeOptionsPage,
)


def page(rows, query, schema, item):
    return schema(
        items=[item.model_validate(row) for row in rows[: query.limit]],
        next_cursor=rows[query.limit - 1]["id"] if len(rows) > query.limit else None,
    )


class CatalogEditorOptions:
    @staticmethod
    async def models(session: AsyncSession, query: EditorOptionsQuery):
        return page(
            await EditorOptionRepository.models(session, query),
            query,
            ModelOptionsPage,
            ModelOption,
        )

    @staticmethod
    async def model(
        session: AsyncSession, model_id: int, selected_size_ids: list[int] | None = None
    ):
        row = await EditorOptionRepository.model(session, model_id)
        if row is None:
            return None
        sizes = await EditorOptionRepository.selected_sizes(
            session, model_id, selected_size_ids or []
        )
        return EditorModel.model_validate({**row, "sizes": sizes})

    @staticmethod
    async def sizes(session: AsyncSession, query: EditorSizeQuery):
        return page(
            await EditorOptionRepository.sizes(session, query), query, SizeOptionsPage, SizeOption
        )

    @staticmethod
    async def fabrics(session: AsyncSession, query: EditorOptionsQuery):
        return page(
            await EditorOptionRepository.fabrics(session, query),
            query,
            FabricOptionsPage,
            FabricOption,
        )

    @staticmethod
    async def selected_fabrics(session: AsyncSession, ids: list[int]):
        return [
            FabricOption.model_validate(row)
            for row in await EditorOptionRepository.selected_fabrics(session, ids)
        ]


def editor_options_router(prefix: str, authorize):
    router = APIRouter(prefix=prefix, tags=["catalog-editor"], dependencies=[Depends(authorize)])
    session_type = Annotated[AsyncSession, Depends(get_database_session)]

    @router.get("/models", response_model=ModelOptionsPage)
    async def models(
        response: Response, session: session_type, query: Annotated[EditorOptionsQuery, Query()]
    ):
        response.headers["Cache-Control"] = "no-store"
        return await CatalogEditorOptions.models(session, query)

    @router.get("/models/{model_id}", response_model=EditorModel)
    async def model(
        response: Response,
        session: session_type,
        model_id: Annotated[int, Path(gt=0, le=2_147_483_647)],
        query: Annotated[SelectedSizeQuery, Query()],
    ):
        response.headers["Cache-Control"] = "no-store"
        result = await CatalogEditorOptions.model(session, model_id, query.selected_size_ids)
        if result is None:
            raise HTTPException(404, "Модель не найдена", headers={"Cache-Control": "no-store"})
        return result

    @router.get("/sizes", response_model=SizeOptionsPage)
    async def sizes(
        response: Response, session: session_type, query: Annotated[EditorSizeQuery, Query()]
    ):
        response.headers["Cache-Control"] = "no-store"
        return await CatalogEditorOptions.sizes(session, query)

    @router.get("/fabrics", response_model=FabricOptionsPage)
    async def fabrics(
        response: Response, session: session_type, query: Annotated[EditorOptionsQuery, Query()]
    ):
        response.headers["Cache-Control"] = "no-store"
        return await CatalogEditorOptions.fabrics(session, query)

    @router.get("/selected-fabrics", response_model=list[FabricOption])
    async def selected(
        response: Response, session: session_type, query: Annotated[SelectedFabricQuery, Query()]
    ):
        response.headers["Cache-Control"] = "no-store"
        return await CatalogEditorOptions.selected_fabrics(session, query.ids)

    return router
