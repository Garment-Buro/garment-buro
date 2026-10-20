from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.catalog.storefront_schemas import PositiveId
from app.modules.identity.models import User
from app.modules.identity.router import get_current_identity_user
from app.modules.partners.community_favorite_schemas import (
    CommunityFavoritePageResponse,
    CommunityFavoriteStatusResponse,
)
from app.modules.partners.community_favorite_service import (
    CommunityFavoriteService,
    CommunityUnavailableError,
)

router = APIRouter(prefix="/api/profile/community-favorites", tags=["community favorites"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
CurrentUser = Annotated[User, Depends(get_current_identity_user)]
LandingId = Annotated[int, Path(gt=0, le=2_147_483_647)]


def get_community_favorite_service() -> CommunityFavoriteService:
    return CommunityFavoriteService()


Service = Annotated[CommunityFavoriteService, Depends(get_community_favorite_service)]


@router.get("/status", response_model=CommunityFavoriteStatusResponse)
async def community_favorite_status(
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
    community_ids: Annotated[list[PositiveId], Query(min_length=1, max_length=100)],
):
    response.headers["Cache-Control"] = "no-store"
    return CommunityFavoriteStatusResponse(
        community_ids=await service.status(
            session,
            user_id=user.id,
            landing_ids=community_ids,
        )
    )


@router.get("", response_model=CommunityFavoritePageResponse)
async def community_favorites(
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    cursor: Annotated[int | None, Query(gt=0, le=2_147_483_647)] = None,
):
    response.headers["Cache-Control"] = "no-store"
    return await service.list_page(session, user_id=user.id, limit=limit, cursor=cursor)


@router.put("/{landing_id}", status_code=204)
async def add_community_favorite(
    landing_id: LandingId, session: Session, user: CurrentUser, service: Service
):
    try:
        await service.add(session, user_id=user.id, landing_id=landing_id)
        await session.commit()
    except CommunityUnavailableError as error:
        raise HTTPException(status_code=404, detail="Community not found") from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Favorite write conflict") from error
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.delete("/{landing_id}", status_code=204)
async def remove_community_favorite(
    landing_id: LandingId, session: Session, user: CurrentUser, service: Service
):
    await service.remove(session, user_id=user.id, landing_id=landing_id)
    await session.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
