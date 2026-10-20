from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.catalog.schemas import ProductCategoryResponse
from app.modules.crm.category_directory_schemas import (
    CategoryDirectoryQuery,
    CategoryKind,
    CategoryPage,
)
from app.modules.crm.category_directory_service import CategoryDirectoryService
from app.modules.crm.directory_api import read_reference_page
from app.modules.crm.reference_schemas import CrmGarmentModelCategoryRead

Session = Annotated[AsyncSession, Depends(get_database_session)]
Identity = Annotated[int, Path(gt=0, le=2_147_483_647)]


def category_directory_router(authorize):
    router = APIRouter(dependencies=[Depends(authorize)])

    @router.get("/directory/categories/{kind}", response_model=CategoryPage)
    async def page(
        kind: CategoryKind,
        response: Response,
        session: Session,
        query: Annotated[CategoryDirectoryQuery, Query()],
    ):
        return await read_reference_page(
            response, CategoryDirectoryService().page(session, kind, query)
        )

    async def detail(kind, identity, response, session):
        response.headers["Cache-Control"] = "no-store"
        row = await CategoryDirectoryService().detail(session, kind, identity)
        if row is None:
            raise HTTPException(404, "Категория не найдена", headers={"Cache-Control": "no-store"})
        return row

    @router.get("/model-categories/{category_id}", response_model=CrmGarmentModelCategoryRead)
    async def model(category_id: Identity, response: Response, session: Session):
        return await detail("model-categories", category_id, response, session)

    @router.get("/product-categories/{category_id}", response_model=ProductCategoryResponse)
    async def product(category_id: Identity, response: Response, session: Session):
        return await detail("product-categories", category_id, response, session)

    return router
