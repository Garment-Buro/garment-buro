"""Community owners edit existing partner landings, never a second collection store."""

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.identity.models import PermissionCode, User
from app.modules.identity.router import get_current_identity_user, get_identity_service
from app.modules.identity.service import IdentityService
from app.modules.partners.models import PartnerProfile
from app.modules.partners.owner_schemas import (
    OwnerLandingCard,
    OwnerLandingPage,
    OwnerLandingPosition,
    OwnerLandingQuery,
)
from app.modules.partners.router import _require_permission, get_partner_service
from app.modules.partners.schemas import (
    PartnerLandingCreateRequest,
    PartnerLandingResponse,
    PartnerLandingUpdateRequest,
)
from app.modules.partners.service import (
    PartnerConflictError,
    PartnerLandingEmptyCollectionError,
    PartnerLandingNotFoundError,
    PartnerLandingProductNotFoundError,
    PartnerLandingVersionConflictError,
    PartnerNotFoundError,
    PartnerProgramDisabledError,
    PartnerProgramService,
)

router = APIRouter(prefix="/api/partner/own-landings", tags=["partner-owner-landings"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
Service = Annotated[PartnerProgramService, Depends(get_partner_service)]


def command_error(error: Exception) -> HTTPException:
    headers = {"Cache-Control": "no-store"}
    if isinstance(error, PartnerLandingVersionConflictError):
        return HTTPException(409, detail={"code": "landing_version_conflict"}, headers=headers)
    if isinstance(
        error, (PartnerLandingNotFoundError, PartnerNotFoundError, PartnerProgramDisabledError)
    ):
        return HTTPException(404, detail="Partner landing was not found", headers=headers)
    if isinstance(error, PartnerLandingProductNotFoundError):
        return HTTPException(
            422,
            detail={"code": "collection_products_unavailable", "product_ids": error.product_ids},
            headers=headers,
        )
    if isinstance(error, PartnerLandingEmptyCollectionError):
        return HTTPException(422, detail={"code": "collection_empty"}, headers=headers)
    if isinstance(error, PartnerConflictError):
        return HTTPException(409, detail={"code": "landing_slug_conflict"}, headers=headers)
    if isinstance(error, IntegrityError):
        # A competing create can win after the slug precheck. Other integrity
        # errors must not be mislabeled as address collisions.
        constraint = getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)
        if (
            constraint == "uq_partner_landings_slug"
            or "UNIQUE constraint failed: partner_landings.slug" in str(error.orig)
        ):
            return HTTPException(409, detail={"code": "landing_slug_conflict"}, headers=headers)
    return HTTPException(503, detail="Partner landing is unavailable", headers=headers)


async def owner_profile(
    response: Response,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Session,
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Service,
) -> PartnerProfile:
    response.headers["Cache-Control"] = "no-store"
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_READ_OWN)
    try:
        service.require_enabled()
        profile = await service.repository.get_active_profile_by_user(session, user_id=user.id)
        if profile is None:
            raise PartnerNotFoundError("Active partner profile was not found")
        return profile
    except (PartnerNotFoundError, PartnerProgramDisabledError) as error:
        raise command_error(error) from error


Owner = Annotated[PartnerProfile, Depends(owner_profile)]


@router.get("", response_model=OwnerLandingPage)
async def list_owned_landings(
    query: Annotated[OwnerLandingQuery, Query()], owner: Owner, session: Session, service: Service
):
    after_id = None
    if query.cursor is not None:
        try:
            position = OwnerLandingPosition.model_validate_json(
                base64.b64decode(query.cursor, altchars=b"-_", validate=True)
            )
            if position.partner_id != owner.id:
                raise ValueError("Cursor belongs to another owner")
            after_id = position.id
        except (ValueError, ValidationError) as error:
            raise HTTPException(
                422, detail={"code": "invalid_cursor"}, headers={"Cache-Control": "no-store"}
            ) from error
    rows = await service.repository.list_owned_landing_page(
        session, partner_id=owner.id, limit=query.limit, after_id=after_id
    )
    page = rows[: query.limit]
    cursor = None
    if len(rows) > query.limit:
        cursor = base64.urlsafe_b64encode(
            OwnerLandingPosition(version=1, partner_id=owner.id, id=page[-1]["id"])
            .model_dump_json()
            .encode()
        ).decode()
    return OwnerLandingPage(
        items=[OwnerLandingCard.model_validate(row) for row in page], next_cursor=cursor
    )


@router.get("/{landing_id}", response_model=PartnerLandingResponse)
async def read_owned_landing(landing_id: int, owner: Owner, session: Session, service: Service):
    landing = await service.repository.get_landing(
        session, landing_id=landing_id, partner_id=owner.id
    )
    if landing is None:
        raise command_error(PartnerLandingNotFoundError())
    return PartnerLandingResponse.model_validate(landing)


@router.post("", response_model=PartnerLandingResponse, status_code=201)
async def create_owned_landing(
    payload: PartnerLandingCreateRequest, owner: Owner, session: Session, service: Service
):
    try:
        landing = await service.create_landing(
            session, owner_user_id=owner.user_id, payload=payload
        )
        await session.commit()
    except (
        PartnerProgramDisabledError,
        PartnerNotFoundError,
        PartnerConflictError,
        PartnerLandingProductNotFoundError,
        PartnerLandingEmptyCollectionError,
        SQLAlchemyError,
    ) as error:
        await session.rollback()
        raise command_error(error) from error
    return PartnerLandingResponse.model_validate(landing)


@router.patch("/{landing_id}", response_model=PartnerLandingResponse)
async def update_owned_landing(
    landing_id: int,
    payload: PartnerLandingUpdateRequest,
    owner: Owner,
    session: Session,
    service: Service,
):
    try:
        landing = await service.update_landing(
            session, landing_id=landing_id, owner_user_id=owner.user_id, payload=payload
        )
        await session.commit()
    except (
        PartnerProgramDisabledError,
        PartnerNotFoundError,
        PartnerLandingNotFoundError,
        PartnerConflictError,
        PartnerLandingProductNotFoundError,
        PartnerLandingEmptyCollectionError,
        SQLAlchemyError,
    ) as error:
        await session.rollback()
        raise command_error(error) from error
    return PartnerLandingResponse.model_validate(landing)
