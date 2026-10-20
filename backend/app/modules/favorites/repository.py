from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product
from app.modules.catalog.public_policy import public_product_ids
from app.modules.favorites.models import UserFavorite


class FavoriteRepository:
    async def product_is_available(self, session: AsyncSession, *, product_id: int) -> bool:
        return (
            await session.scalar(public_product_ids().where(Product.id == product_id)) is not None
        )

    async def add(self, session: AsyncSession, *, user_id: int, product_id: int) -> None:
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgresql_insert(UserFavorite)
        elif dialect == "sqlite":
            statement = sqlite_insert(UserFavorite)
        else:
            raise RuntimeError("Persistent favorites require PostgreSQL or SQLite")
        await session.execute(
            statement.values(user_id=user_id, product_id=product_id).on_conflict_do_nothing(
                index_elements=[UserFavorite.user_id, UserFavorite.product_id]
            )
        )

    async def list_page(
        self, session: AsyncSession, *, user_id: int, limit: int, cursor: int | None
    ) -> list[UserFavorite]:
        statement = select(UserFavorite).where(
            UserFavorite.user_id == user_id,
            UserFavorite.product_id.in_(public_product_ids()),
        )
        if cursor is not None:
            statement = statement.where(UserFavorite.id < cursor)
        result = await session.scalars(statement.order_by(UserFavorite.id.desc()).limit(limit))
        return list(result)

    async def status(
        self, session: AsyncSession, *, user_id: int, product_ids: list[int]
    ) -> list[int]:
        return list(
            await session.scalars(
                select(UserFavorite.product_id)
                .where(
                    UserFavorite.user_id == user_id,
                    UserFavorite.product_id.in_(product_ids),
                    UserFavorite.product_id.in_(public_product_ids()),
                )
                .order_by(UserFavorite.product_id)
            )
        )

    async def remove(self, session: AsyncSession, *, user_id: int, product_id: int) -> None:
        await session.execute(
            delete(UserFavorite).where(
                UserFavorite.user_id == user_id, UserFavorite.product_id == product_id
            )
        )
