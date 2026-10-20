from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import invalid_cursor_error
from app.db.session import get_database_session
from app.modules.identity.models import User
from app.modules.identity.router import get_current_identity_user
from app.modules.public_profiles.schemas import (
    OwnPublicProfileResponse,
    PeoplePageResponse,
    PeopleQuery,
    ProfileSlug,
    PublicProfileResponse,
    PublicProfileWrite,
)
from app.modules.public_profiles.service import (
    InvalidPeopleCursor,
    ProfileConflictError,
    ProfileUnavailableError,
    PublicProfileService,
)

router = APIRouter(tags=["public-profiles"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
CurrentUser = Annotated[User, Depends(get_current_identity_user)]


def get_profile_service() -> PublicProfileService:
    return PublicProfileService()


Service = Annotated[PublicProfileService, Depends(get_profile_service)]


@router.get("/api/people", response_model=PeoplePageResponse)
async def list_people(
    response: Response, query: Annotated[PeopleQuery, Query()], session: Session, service: Service
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return await service.list_page(session, query)
    except InvalidPeopleCursor as error:
        raise invalid_cursor_error() from error


@router.get("/api/people/{slug}", response_model=PublicProfileResponse)
async def read_person(slug: ProfileSlug, response: Response, session: Session, service: Service):
    response.headers["Cache-Control"] = "no-store"
    try:
        return await service.public(session, slug)
    except ProfileUnavailableError as error:
        # Exceptions build a new response; preserve revocation headers there too.
        raise HTTPException(
            status_code=404,
            detail="Public profile not found",
            headers={"Cache-Control": "no-store"},
        ) from error


@router.get("/api/profile/public", response_model=OwnPublicProfileResponse | None)
async def read_own_public_profile(
    response: Response, session: Session, user: CurrentUser, service: Service
):
    response.headers["Cache-Control"] = "no-store"
    return await service.own(session, user.id)


@router.put("/api/profile/public", response_model=OwnPublicProfileResponse)
async def save_public_profile(
    body: PublicProfileWrite,
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
):
    response.headers["Cache-Control"] = "no-store"
    try:
        profile = await service.save(session, user.id, body)
        await session.commit()
        return profile
    except (ProfileConflictError, IntegrityError) as error:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Public profile changed or address unavailable"
        ) from error
    except ProfileUnavailableError as error:
        raise HTTPException(status_code=404, detail="Account unavailable") from error
