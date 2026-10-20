from fastapi import HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.partners.admin_directory_schemas import AdminLandingPage, AdminLandingQuery
from app.modules.partners.admin_directory_service import (
    AdminLandingService,
    InvalidAdminLandingCursor,
)


async def read_admin_landing_page(
    response: Response, session: AsyncSession, query: AdminLandingQuery
) -> AdminLandingPage:
    response.headers["Cache-Control"] = "no-store"
    try:
        return await AdminLandingService.list_page(session, query)
    except InvalidAdminLandingCursor as error:
        raise HTTPException(
            422,
            detail={"code": "invalid_cursor", "message": "Обновите список лендингов."},
            headers={"Cache-Control": "no-store"},
        ) from error
