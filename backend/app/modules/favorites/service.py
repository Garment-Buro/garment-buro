from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.favorites.repository import FavoriteRepository
from app.modules.favorites.schemas import FavoriteItemResponse, FavoritePageResponse
from app.modules.identity.customer_writes import lock_active_customer
from app.modules.identity.security import ensure_utc


class FavoriteProductUnavailableError(Exception):
    pass


class FavoriteService:
    def __init__(self, repository: FavoriteRepository | None = None) -> None:
        self.repository = repository or FavoriteRepository()

    async def add(self, session: AsyncSession, *, user_id: int, product_id: int) -> None:
        if not await lock_active_customer(session, user_id):
            raise FavoriteProductUnavailableError
        if not await self.repository.product_is_available(session, product_id=product_id):
            raise FavoriteProductUnavailableError
        await self.repository.add(session, user_id=user_id, product_id=product_id)

    async def list_page(
        self, session: AsyncSession, *, user_id: int, limit: int, cursor: int | None
    ) -> FavoritePageResponse:
        records = await self.repository.list_page(
            session, user_id=user_id, limit=limit + 1, cursor=cursor
        )
        page = records[:limit]
        return FavoritePageResponse(
            items=[
                FavoriteItemResponse(
                    product_id=record.product_id, saved_at=ensure_utc(record.created_at)
                )
                for record in page
            ],
            next_cursor=page[-1].id if len(records) > limit else None,
        )

    async def remove(self, session: AsyncSession, *, user_id: int, product_id: int) -> None:
        await self.repository.remove(session, user_id=user_id, product_id=product_id)

    async def status(
        self, session: AsyncSession, *, user_id: int, product_ids: list[int]
    ) -> list[int]:
        return await self.repository.status(session, user_id=user_id, product_ids=product_ids)
