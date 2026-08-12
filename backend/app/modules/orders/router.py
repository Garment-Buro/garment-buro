from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.identity.exceptions import PermissionDeniedError
from app.modules.identity.models import PermissionCode, User
from app.modules.identity.router import get_current_identity_user, get_identity_service
from app.modules.identity.service import IdentityService
from app.modules.orders.schemas import LegacyOrderResponse
from app.modules.orders.security import InvalidOrderGuestAccessTokenError
from app.modules.orders.service import OrderGuestAccessService, TargetOrderReadService

router = APIRouter(prefix="/api/orders", tags=["orders"])
guest_router = APIRouter(prefix="/api/order-access", tags=["orders"])


def get_target_order_read_service(request: Request) -> TargetOrderReadService:
    service = request.app.state.target_order_read_service
    if service is None:
        raise RuntimeError("Target order read service is not initialized")
    return service


def get_order_guest_access_service(request: Request) -> OrderGuestAccessService:
    service = request.app.state.order_guest_access_service
    if service is None:
        raise RuntimeError("Order guest access service is not initialized")
    return service


@guest_router.get("", response_model=LegacyOrderResponse)
async def get_guest_order(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[OrderGuestAccessService, Depends(get_order_guest_access_service)],
    access_token: Annotated[
        str | None,
        Header(alias="X-Order-Access-Token"),
    ] = None,
) -> LegacyOrderResponse:
    try:
        order = (
            await service.resolve(session, token=access_token) if access_token is not None else None
        )
    except InvalidOrderGuestAccessTokenError:
        order = None
    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
            headers={"Cache-Control": "no-store"},
        )
    response.headers["Cache-Control"] = "no-store"
    return order


@router.get("", response_model=list[LegacyOrderResponse])
async def list_orders(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[TargetOrderReadService, Depends(get_target_order_read_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[LegacyOrderResponse]:
    await _require_permission(
        identity,
        session,
        user.id,
        PermissionCode.ORDERS_READ_ALL,
    )
    return await service.list_all_orders(
        session,
        limit=limit,
        offset=offset,
    )


@router.get("/{order_id}", response_model=LegacyOrderResponse)
async def get_order(
    order_id: int,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    service: Annotated[TargetOrderReadService, Depends(get_target_order_read_service)],
) -> LegacyOrderResponse:
    if await _has_permission(
        identity,
        session,
        user.id,
        PermissionCode.ORDERS_READ_ALL,
    ):
        order = await service.get_order(session, order_id=order_id)
    else:
        await _require_permission(
            identity,
            session,
            user.id,
            PermissionCode.ORDERS_READ_OWN,
        )
        order = await service.get_owned_order(
            session,
            user=user,
            order_id=order_id,
        )
        await session.commit()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def _has_permission(
    identity: IdentityService,
    session: AsyncSession,
    user_id: int,
    permission: PermissionCode,
) -> bool:
    try:
        await identity.require_permission(
            session,
            user_id=user_id,
            permission=permission,
        )
    except PermissionDeniedError:
        return False
    return True


async def _require_permission(
    identity: IdentityService,
    session: AsyncSession,
    user_id: int,
    permission: PermissionCode,
) -> None:
    if not await _has_permission(identity, session, user_id, permission):
        raise HTTPException(status_code=403, detail="Forbidden")
