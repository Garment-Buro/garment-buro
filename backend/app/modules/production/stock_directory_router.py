"""Bounded stock reads use the calling production surface's existing authority."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.crm.directory_api import read_reference_page
from app.modules.crm.stock_directory_schemas import (
    AccessoryCategoryPage,
    AccessoryCategoryQuery,
    AccessoryDirectoryPage,
    AccessoryDirectoryQuery,
    AccessoryRequirementPage,
    AccessoryRequirementQuery,
    BoxDirectoryPage,
    BoxDirectoryQuery,
    PackagingRulePage,
    PackagingRuleQuery,
)
from app.modules.crm.stock_directory_service import StockDirectoryService

Session = Annotated[AsyncSession, Depends(get_database_session)]


def stock_directory_router(authorize):
    router = APIRouter(prefix="/directory", dependencies=[Depends(authorize)])

    @router.get("/accessories", response_model=AccessoryDirectoryPage)
    async def accessories(
        response: Response, session: Session, query: Annotated[AccessoryDirectoryQuery, Query()]
    ):
        return await read_reference_page(
            response, StockDirectoryService().page(session, "accessories", query)
        )

    @router.get("/boxes", response_model=BoxDirectoryPage)
    async def boxes(
        response: Response, session: Session, query: Annotated[BoxDirectoryQuery, Query()]
    ):
        return await read_reference_page(
            response, StockDirectoryService().page(session, "boxes", query)
        )

    @router.get("/accessory-categories", response_model=AccessoryCategoryPage)
    async def categories(
        response: Response, session: Session, query: Annotated[AccessoryCategoryQuery, Query()]
    ):
        return await read_reference_page(
            response, StockDirectoryService().page(session, "accessory-categories", query)
        )

    @router.get("/accessory-requirements", response_model=AccessoryRequirementPage)
    async def requirements(
        response: Response, session: Session, query: Annotated[AccessoryRequirementQuery, Query()]
    ):
        return await read_reference_page(
            response, StockDirectoryService().page(session, "accessory-requirements", query)
        )

    @router.get("/packaging-rules", response_model=PackagingRulePage)
    async def rules(
        response: Response, session: Session, query: Annotated[PackagingRuleQuery, Query()]
    ):
        return await read_reference_page(
            response, StockDirectoryService().page(session, "packaging-rules", query)
        )

    return router
