from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.carts.schemas import (
    CartDeletedResponse,
    CartSnapshotResponse,
    CartUpdatedResponse,
    CartUpdateRequest,
)
from app.modules.carts.security import InvalidCartIdError
from app.modules.carts.service import CartService, CartTimestampError

router = APIRouter(prefix="/api/cart", tags=["carts"])


def get_cart_service(request: Request) -> CartService:
    return CartService(request.app.state.settings)


@router.get(
    "/{cart_id}",
    response_model=CartSnapshotResponse,
    response_model_exclude_none=True,
)
async def get_cart(
    cart_id: str,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartSnapshotResponse:
    try:
        return await service.get_snapshot(session, cart_id=cart_id)
    except InvalidCartIdError as error:
        raise HTTPException(status_code=400, detail="Invalid cart id") from error


@router.put("/{cart_id}", response_model=CartUpdatedResponse)
async def upsert_cart(
    cart_id: str,
    payload: CartUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartUpdatedResponse:
    try:
        updated = await service.upsert_snapshot(
            session,
            cart_id=cart_id,
            payload=payload,
        )
        await session.commit()
        return updated
    except InvalidCartIdError as error:
        raise HTTPException(status_code=400, detail="Invalid cart id") from error
    except CartTimestampError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Cart write conflict") from error


@router.delete("/{cart_id}", response_model=CartDeletedResponse)
async def delete_cart(
    cart_id: str,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartDeletedResponse:
    try:
        deleted = await service.delete_snapshot(session, cart_id=cart_id)
        await session.commit()
        return deleted
    except InvalidCartIdError as error:
        raise HTTPException(status_code=400, detail="Invalid cart id") from error
