from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppEnvironment
from app.db.session import get_database_session
from app.modules.identity.exceptions import PermissionDeniedError
from app.modules.identity.models import PermissionCode, User
from app.modules.identity.router import get_current_identity_user, get_identity_service
from app.modules.identity.service import IdentityService
from app.modules.partners.schemas import (
    PartnerCommissionResponse,
    PartnerCreateRequest,
    PartnerDashboardResponse,
    PartnerLandingCreateRequest,
    PartnerLandingResponse,
    PartnerLandingUpdateRequest,
    PartnerPayoutCreateRequest,
    PartnerPayoutResponse,
    PartnerPayoutReviewRequest,
    PartnerProfileResponse,
    PartnerUpdateRequest,
    PartnerVisitResponse,
    PublicPartnerLandingResponse,
)
from app.modules.partners.service import (
    PartnerConflictError,
    PartnerLandingNotFoundError,
    PartnerNotFoundError,
    PartnerPayoutBalanceError,
    PartnerPayoutStateError,
    PartnerProgramDisabledError,
    PartnerProgramService,
)

public_router = APIRouter(prefix="/api/partner/landings", tags=["partner-public"])
partner_router = APIRouter(prefix="/api/partner", tags=["partner"])
admin_router = APIRouter(prefix="/api/admin/partners", tags=["partner-admin"])


def get_partner_service(request: Request) -> PartnerProgramService:
    service = request.app.state.partner_program_service
    if not isinstance(service, PartnerProgramService):
        raise RuntimeError("Partner program service is not initialized")
    return service


@public_router.get("/{slug}", response_model=PublicPartnerLandingResponse)
async def get_public_landing(
    slug: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PublicPartnerLandingResponse:
    try:
        result = await service.public_landing(session, slug=slug)
    except PartnerProgramDisabledError as error:
        raise HTTPException(status_code=404, detail="Partner landing was not found") from error
    except PartnerLandingNotFoundError as error:
        raise HTTPException(status_code=404, detail="Partner landing was not found") from error
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return result


@public_router.post("/{slug}/visits", response_model=PartnerVisitResponse)
async def register_public_visit(
    slug: str,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PartnerVisitResponse:
    settings = request.app.state.settings
    visitor_cookie = request.cookies.get(settings.partner_visitor_cookie_name)
    visitor_value = visitor_cookie or secrets.token_urlsafe(24)
    try:
        token, expires_at = await service.register_visit(
            session,
            slug=slug,
            visitor_value=visitor_value,
            now=datetime.now(timezone.utc),
        )
        await session.commit()
    except (PartnerProgramDisabledError, PartnerLandingNotFoundError) as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Partner landing was not found") from error
    except SQLAlchemyError as error:
        await session.rollback()
        raise HTTPException(status_code=503, detail="Partner tracking is unavailable") from error

    secure = settings.app_env in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}
    cookie_options = {
        "max_age": settings.partner_attribution_days * 86_400,
        "expires": expires_at,
        "path": "/",
        "secure": secure,
        "httponly": True,
        "samesite": "lax",
    }
    if settings.partner_cookie_domain:
        cookie_options["domain"] = settings.partner_cookie_domain
    response.set_cookie(
        key=settings.partner_attribution_cookie_name,
        value=token,
        **cookie_options,
    )
    if visitor_cookie is None:
        response.set_cookie(
            key=settings.partner_visitor_cookie_name,
            value=visitor_value,
            **cookie_options,
        )
    response.headers["Cache-Control"] = "no-store"
    return PartnerVisitResponse()


@partner_router.get("/me", response_model=PartnerProfileResponse)
async def get_partner_profile(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PartnerProfileResponse:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_READ_OWN)
    try:
        profile = await service.get_partner_for_user(session, user_id=user.id)
    except (PartnerProgramDisabledError, PartnerNotFoundError) as error:
        raise HTTPException(status_code=404, detail="Partner profile was not found") from error
    return PartnerProfileResponse.model_validate(profile)


@partner_router.get("/dashboard", response_model=PartnerDashboardResponse)
async def get_partner_dashboard(
    response: Response,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PartnerDashboardResponse:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_READ_OWN)
    try:
        dashboard = await service.dashboard(session, user_id=user.id)
    except (PartnerProgramDisabledError, PartnerNotFoundError) as error:
        raise HTTPException(status_code=404, detail="Partner profile was not found") from error
    response.headers["Cache-Control"] = "no-store"
    return dashboard


@partner_router.get("/landings", response_model=list[PartnerLandingResponse])
async def list_partner_landings(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> list[PartnerLandingResponse]:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_READ_OWN)
    profile = await _partner_profile(service, session, user.id)
    landings = await service.repository.list_landings(session, partner_id=profile.id)
    return [PartnerLandingResponse.model_validate(landing) for landing in landings]


@partner_router.get("/commissions", response_model=list[PartnerCommissionResponse])
async def list_partner_commissions(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> list[PartnerCommissionResponse]:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_READ_OWN)
    profile = await _partner_profile(service, session, user.id)
    commissions = await service.repository.list_partner_commissions(
        session,
        partner_id=profile.id,
    )
    return [PartnerCommissionResponse.model_validate(item) for item in commissions]


@partner_router.get("/payouts", response_model=list[PartnerPayoutResponse])
async def list_partner_payouts(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> list[PartnerPayoutResponse]:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_READ_OWN)
    profile = await _partner_profile(service, session, user.id)
    payouts = await service.repository.list_partner_payouts(session, partner_id=profile.id)
    return [PartnerPayoutResponse.model_validate(item) for item in payouts]


@partner_router.post(
    "/payouts",
    response_model=PartnerPayoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_partner_payout(
    payload: PartnerPayoutCreateRequest,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PartnerPayoutResponse:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_READ_OWN)
    try:
        payout = await service.request_payout(
            session,
            user_id=user.id,
            amount=payload.amount,
        )
        await session.commit()
    except PartnerPayoutBalanceError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Insufficient available balance") from error
    except (PartnerProgramDisabledError, PartnerNotFoundError) as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Partner profile was not found") from error
    return PartnerPayoutResponse.model_validate(payout)


@admin_router.post("", response_model=PartnerProfileResponse, status_code=201)
async def create_partner(
    payload: PartnerCreateRequest,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PartnerProfileResponse:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_MANAGE)
    try:
        partner = await service.create_partner(
            session,
            payload=payload,
            actor_user_id=user.id,
        )
        await session.commit()
    except (PartnerConflictError, IntegrityError) as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Partner already exists") from error
    return PartnerProfileResponse.model_validate(partner)


@admin_router.get("", response_model=list[PartnerProfileResponse])
async def list_partners(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> list[PartnerProfileResponse]:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_MANAGE)
    try:
        service.require_enabled()
    except PartnerProgramDisabledError as error:
        raise HTTPException(status_code=404, detail="Partner program is disabled") from error
    profiles = await service.repository.list_profiles(session)
    return [PartnerProfileResponse.model_validate(profile) for profile in profiles]


@admin_router.patch("/{partner_id}", response_model=PartnerProfileResponse)
async def update_partner(
    partner_id: int,
    payload: PartnerUpdateRequest,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PartnerProfileResponse:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_MANAGE)
    try:
        partner = await service.update_partner(
            session,
            partner_id=partner_id,
            payload=payload,
        )
        await session.commit()
    except PartnerNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Partner profile was not found") from error
    return PartnerProfileResponse.model_validate(partner)


@admin_router.post(
    "/{partner_id}/landings",
    response_model=PartnerLandingResponse,
    status_code=201,
)
async def create_partner_landing(
    partner_id: int,
    payload: PartnerLandingCreateRequest,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PartnerLandingResponse:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_MANAGE)
    try:
        landing = await service.create_landing(
            session,
            partner_id=partner_id,
            payload=payload,
        )
        await session.commit()
    except PartnerNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Partner profile was not found") from error
    except (PartnerConflictError, IntegrityError) as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Landing slug is already used") from error
    return PartnerLandingResponse.model_validate(landing)


@admin_router.get("/landings", response_model=list[PartnerLandingResponse])
async def list_admin_landings(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> list[PartnerLandingResponse]:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_MANAGE)
    try:
        service.require_enabled()
    except PartnerProgramDisabledError as error:
        raise HTTPException(status_code=404, detail="Partner program is disabled") from error
    landings = await service.repository.list_all_landings(session)
    return [PartnerLandingResponse.model_validate(landing) for landing in landings]


@admin_router.patch("/landings/{landing_id}", response_model=PartnerLandingResponse)
async def update_partner_landing(
    landing_id: int,
    payload: PartnerLandingUpdateRequest,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PartnerLandingResponse:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_MANAGE)
    try:
        landing = await service.update_landing(
            session,
            landing_id=landing_id,
            payload=payload,
        )
        await session.commit()
    except PartnerLandingNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Partner landing was not found") from error
    return PartnerLandingResponse.model_validate(landing)


@admin_router.patch("/payouts/{payout_id}", response_model=PartnerPayoutResponse)
async def review_partner_payout(
    payout_id: int,
    payload: PartnerPayoutReviewRequest,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> PartnerPayoutResponse:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_MANAGE)
    try:
        payout = await service.review_payout(
            session,
            payout_id=payout_id,
            status=payload.status,
            note=payload.note,
            actor_user_id=user.id,
        )
        await session.commit()
    except PartnerNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Payout request was not found") from error
    except PartnerPayoutStateError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Invalid payout status transition") from error
    return PartnerPayoutResponse.model_validate(payout)


async def _partner_profile(
    service: PartnerProgramService,
    session: AsyncSession,
    user_id: int,
):
    try:
        return await service.get_partner_for_user(session, user_id=user_id)
    except (PartnerProgramDisabledError, PartnerNotFoundError) as error:
        raise HTTPException(status_code=404, detail="Partner profile was not found") from error


async def _require_permission(
    identity: IdentityService,
    session: AsyncSession,
    user_id: int,
    permission: PermissionCode,
) -> None:
    try:
        await identity.require_permission(session, user_id=user_id, permission=permission)
    except PermissionDeniedError as error:
        raise HTTPException(status_code=403, detail="Forbidden") from error
