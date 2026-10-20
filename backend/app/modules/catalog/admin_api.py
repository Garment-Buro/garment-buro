"""HTTP adapters shared by identity staff and production management routes."""

from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.admin_schemas import CatalogAdminPage, CatalogAdminQuery
from app.modules.catalog.admin_service import CatalogAdminReadService, InvalidCatalogAdminCursor
from app.modules.catalog.editor_media import (
    CatalogEditorMediaLimitError,
    catalog_editor_media_limit_detail,
)
from app.modules.catalog.editor_repository import (
    CatalogEditorVariantLimitError,
    catalog_editor_variant_limit_detail,
)
from app.modules.catalog.mapper import CatalogResponseMapper


def get_catalog_admin_service(request: Request) -> CatalogAdminReadService:
    return CatalogAdminReadService(CatalogResponseMapper(request.app.state.settings))


async def read_catalog_admin_page(
    response: Response,
    session: AsyncSession,
    service: CatalogAdminReadService,
    query: CatalogAdminQuery,
    *,
    include_communities: bool = False,
) -> CatalogAdminPage:
    response.headers["Cache-Control"] = "no-store"
    try:
        return await service.list_page(session, query, include_communities=include_communities)
    except InvalidCatalogAdminCursor as error:
        raise HTTPException(
            422,
            detail={"code": "invalid_cursor", "message": "Обновите список."},
            headers={"Cache-Control": "no-store"},
        ) from error


async def read_catalog_admin_detail(
    response: Response, session: AsyncSession, service: CatalogAdminReadService, product_id: int
):
    response.headers["Cache-Control"] = "no-store"
    try:
        detail = await service.detail(session, product_id)
    except CatalogEditorVariantLimitError as error:
        raise HTTPException(
            409,
            detail=catalog_editor_variant_limit_detail(),
            headers={"Cache-Control": "no-store"},
        ) from error
    except CatalogEditorMediaLimitError as error:
        raise HTTPException(
            409, detail=catalog_editor_media_limit_detail(), headers={"Cache-Control": "no-store"}
        ) from error
    finally:
        # The DTO is fully materialized. Release the source's FOR SHARE before JSON
        # serialization/network backpressure; this read must not commit other work.
        await session.rollback()
    if detail is None:
        raise HTTPException(404, "Product not found", headers={"Cache-Control": "no-store"})
    return detail
