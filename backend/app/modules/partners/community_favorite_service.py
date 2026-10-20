from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.customer_writes import lock_active_customer
from app.modules.partners.community_favorite_repository import CommunityFavoriteRepository
from app.modules.partners.community_favorite_schemas import CommunityFavoritePageResponse
from app.modules.partners.directory_schemas import CommunityCardResponse


class CommunityUnavailableError(Exception):
    pass


class CommunityFavoriteService:
    def __init__(self, repository: CommunityFavoriteRepository | None = None):
        self.repository = repository or CommunityFavoriteRepository()

    async def add(self, session: AsyncSession, *, user_id: int, landing_id: int) -> None:
        if not await lock_active_customer(session, user_id):
            raise CommunityUnavailableError
        if not await self.repository.is_available(session, landing_id):
            raise CommunityUnavailableError
        await self.repository.add(session, user_id=user_id, landing_id=landing_id)

    async def list_page(
        self, session: AsyncSession, *, user_id: int, limit: int, cursor: int | None
    ):
        rows = await self.repository.list_page(
            session, user_id=user_id, limit=limit + 1, cursor=cursor
        )
        page = rows[:limit]
        return CommunityFavoritePageResponse(
            items=[CommunityCardResponse.model_validate(row) for row in page],
            next_cursor=page[-1]["_favorite_id"] if len(rows) > limit else None,
        )

    async def status(
        self, session: AsyncSession, *, user_id: int, landing_ids: list[int]
    ) -> list[int]:
        return await self.repository.status(session, user_id=user_id, landing_ids=landing_ids)

    async def remove(self, session: AsyncSession, *, user_id: int, landing_id: int) -> None:
        await self.repository.remove(session, user_id=user_id, landing_id=landing_id)
