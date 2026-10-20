from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.partners.community_favorite_models import UserCommunityFavorite
from app.modules.partners.directory_repository import public_community_cards
from app.modules.partners.models import PartnerLanding


class CommunityFavoriteRepository:
    async def is_available(self, session: AsyncSession, landing_id: int) -> bool:
        return (
            await session.scalar(
                public_community_cards()
                .with_only_columns(PartnerLanding.id)
                .where(
                    PartnerLanding.id == landing_id,
                )
            )
            is not None
        )

    async def add(self, session: AsyncSession, *, user_id: int, landing_id: int) -> None:
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgresql_insert(UserCommunityFavorite)
        elif dialect == "sqlite":
            statement = sqlite_insert(UserCommunityFavorite)
        else:
            raise RuntimeError("Persistent community favorites require PostgreSQL or SQLite")
        await session.execute(
            statement.values(user_id=user_id, landing_id=landing_id).on_conflict_do_nothing(
                index_elements=[UserCommunityFavorite.user_id, UserCommunityFavorite.landing_id],
            )
        )

    async def list_page(
        self, session: AsyncSession, *, user_id: int, limit: int, cursor: int | None
    ):
        favorite = UserCommunityFavorite
        statement = (
            public_community_cards()
            .add_columns(favorite.id.label("_favorite_id"))
            .join(
                favorite,
                favorite.landing_id == PartnerLanding.id,
            )
            .where(favorite.user_id == user_id)
        )
        if cursor is not None:
            statement = statement.where(favorite.id < cursor)
        return (
            (await session.execute(statement.order_by(favorite.id.desc()).limit(limit)))
            .mappings()
            .all()
        )

    async def status(
        self, session: AsyncSession, *, user_id: int, landing_ids: list[int]
    ) -> list[int]:
        favorite = UserCommunityFavorite
        public_ids = public_community_cards().with_only_columns(PartnerLanding.id)
        return list(
            await session.scalars(
                select(favorite.landing_id)
                .where(
                    favorite.user_id == user_id,
                    favorite.landing_id.in_(landing_ids),
                    favorite.landing_id.in_(public_ids),
                )
                .order_by(favorite.landing_id)
            )
        )

    async def remove(self, session: AsyncSession, *, user_id: int, landing_id: int) -> None:
        await session.execute(
            delete(UserCommunityFavorite).where(
                UserCommunityFavorite.user_id == user_id,
                UserCommunityFavorite.landing_id == landing_id,
            )
        )
