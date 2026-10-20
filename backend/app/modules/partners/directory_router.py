from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import invalid_cursor_error
from app.db.session import get_database_session
from app.modules.partners.directory_schemas import CommunityPageResponse, CommunityQuery
from app.modules.partners.directory_service import CommunityDirectoryService, InvalidCommunityCursor

router = APIRouter(prefix="/api/communities", tags=["communities"])


def get_directory_service() -> CommunityDirectoryService:
    return CommunityDirectoryService()


@router.get("", response_model=CommunityPageResponse)
async def list_communities(
    query: Annotated[CommunityQuery, Query()],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CommunityDirectoryService, Depends(get_directory_service)],
):
    try:
        return await service.list_page(session, query=query)
    except InvalidCommunityCursor as error:
        raise invalid_cursor_error() from error
