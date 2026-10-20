from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.carts.schemas import (
    CartSnapshotResponse,
    CartUpdateRequest,
)
from app.modules.carts.security import InvalidCartIdError
from app.modules.carts.service import CartCatalogItemError, CartRevisionConflictError, CartService
from app.modules.design_assets.security import DesignAssetUnavailableError

router = APIRouter(prefix="/api/cart", tags=["carts"])


def get_cart_service(request: Request) -> CartService:
    return CartService(request.app.state.settings)


@router.get(
    "/{cart_id}",
    response_model=CartSnapshotResponse,
)
async def get_cart(
    cart_id: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartSnapshotResponse:
    try:
        response.headers["Cache-Control"] = "no-store"
        return await service.get_snapshot(session, cart_id=cart_id)
    except InvalidCartIdError as error:
        raise HTTPException(
            status_code=400, detail="Invalid cart id", headers={"Cache-Control": "no-store"}
        ) from error


@router.put("/{cart_id}", response_model=CartSnapshotResponse)
async def upsert_cart(
    cart_id: str,
    payload: CartUpdateRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartSnapshotResponse:
    try:
        response.headers["Cache-Control"] = "no-store"
        updated = await service.upsert_snapshot(
            session,
            cart_id=cart_id,
            payload=payload,
        )
        await session.commit()
        return updated
    except InvalidCartIdError as error:
        raise HTTPException(
            status_code=400, detail="Invalid cart id", headers={"Cache-Control": "no-store"}
        ) from error
    except CartRevisionConflictError as error:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "cart_conflict",
                "message": "Cart changed; choose which snapshot to keep",
            },
            headers={"Cache-Control": "no-store"},
        ) from error
    except CartCatalogItemError as error:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cart product unavailable",
            headers={"Cache-Control": "no-store"},
        ) from error
    except DesignAssetUnavailableError as error:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "cart_design_unavailable",
                "message": "Design image unavailable; upload again",
            },
            headers={"Cache-Control": "no-store"},
        ) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Cart write conflict", headers={"Cache-Control": "no-store"}
        ) from error
