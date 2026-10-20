from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.catalog.storefront_schemas import PositiveId
from app.modules.favorites.schemas import FavoritePageResponse, FavoriteStatusResponse
from app.modules.favorites.service import FavoriteProductUnavailableError, FavoriteService
from app.modules.identity.models import User
from app.modules.identity.router import get_current_identity_user

router = APIRouter(prefix="/api/profile/favorites", tags=["favorites"])


def get_favorite_service() -> FavoriteService:
    return FavoriteService()


Session = Annotated[AsyncSession, Depends(get_database_session)]
CurrentUser = Annotated[User, Depends(get_current_identity_user)]
Service = Annotated[FavoriteService, Depends(get_favorite_service)]
ProductId = Annotated[int, Path(gt=0, le=2_147_483_647)]


@router.get("/status", response_model=FavoriteStatusResponse)
async def favorite_status(
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
    product_ids: Annotated[list[PositiveId], Query(min_length=1, max_length=100)],
) -> FavoriteStatusResponse:
    response.headers["Cache-Control"] = "no-store"
    return FavoriteStatusResponse(
        product_ids=await service.status(
            session,
            user_id=user.id,
            product_ids=product_ids,
        )
    )


@router.get("", response_model=FavoritePageResponse)
async def list_favorites(
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[int | None, Query(gt=0, le=2_147_483_647)] = None,
) -> FavoritePageResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.list_page(session, user_id=user.id, limit=limit, cursor=cursor)


@router.put("/{product_id}", status_code=204)
async def add_favorite(
    product_id: ProductId, session: Session, user: CurrentUser, service: Service
) -> Response:
    try:
        await service.add(session, user_id=user.id, product_id=product_id)
        await session.commit()
    except FavoriteProductUnavailableError as error:
        raise HTTPException(status_code=404, detail="Product not found") from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Favorite write conflict") from error
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.delete("/{product_id}", status_code=204)
async def remove_favorite(
    product_id: ProductId, session: Session, user: CurrentUser, service: Service
) -> Response:
    await service.remove(session, user_id=user.id, product_id=product_id)
    await session.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
