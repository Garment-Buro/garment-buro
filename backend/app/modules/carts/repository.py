from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.modules.carts.models import Cart, CartItem, CartMigrationRun
from app.modules.catalog.models import Product
from app.modules.catalog.public_policy import public_product_ids


class CartRepository:
    async def product_prices(
        self,
        session: AsyncSession,
        product_ids: set[int],
    ) -> dict[int, Decimal]:
        if not product_ids:
            return {}
        return dict(
            (
                await session.execute(
                    select(Product.id, Product.price).where(
                        Product.id.in_(product_ids),
                        Product.id.in_(public_product_ids()),
                    )
                )
            ).all()
        )

    async def get_for_update(
        self,
        session: AsyncSession,
        *,
        token_digest_sha256: str,
    ) -> Cart | None:
        return await session.scalar(
            select(Cart)
            .where(Cart.token_digest_sha256 == token_digest_sha256)
            .options(selectinload(Cart.items))
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def get_active(
        self,
        session: AsyncSession,
        *,
        token_digest_sha256: str,
        now: datetime,
    ) -> Cart | None:
        # One SQL statement gives the revision and all items the same MVCC snapshot.
        result = await session.execute(
            select(Cart)
            .where(Cart.token_digest_sha256 == token_digest_sha256, Cart.expires_at > now)
            .options(joinedload(Cart.items))
        )
        return result.unique().scalar_one_or_none()

    async def acquire(
        self,
        session: AsyncSession,
        *,
        token_digest_sha256: str,
        expires_at: datetime,
    ) -> Cart:
        values = {
            "token_digest_sha256": token_digest_sha256,
            "updated_at_ms": 0,
            "expires_at": expires_at,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(Cart).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(Cart).values(**values)
        else:
            raise RuntimeError("Persistent carts require PostgreSQL or SQLite")
        await session.execute(
            statement.on_conflict_do_nothing(index_elements=[Cart.token_digest_sha256])
        )
        cart = await self.get_for_update(
            session,
            token_digest_sha256=token_digest_sha256,
        )
        if cart is None:
            raise RuntimeError("Cart could not be acquired")
        return cart

    async def list_expired_for_update(
        self,
        session: AsyncSession,
        *,
        now: datetime,
        limit: int,
    ) -> list[Cart]:
        statement = (
            select(Cart)
            .where(Cart.expires_at <= now)
            .options(selectinload(Cart.items))
            .order_by(Cart.expires_at, Cart.id)
            .limit(limit)
        )
        if session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        else:
            statement = statement.with_for_update()
        return list(await session.scalars(statement))

    @staticmethod
    async def replace_items(
        session: AsyncSession,
        cart: Cart,
        items: list[CartItem],
    ) -> None:
        cart.items.clear()
        await session.flush()
        cart.items.extend(items)
        await session.flush()

    @staticmethod
    async def delete_many(session: AsyncSession, carts: list[Cart]) -> None:
        for cart in carts:
            await session.delete(cart)
        await session.flush()

    @staticmethod
    async def target_counts(session: AsyncSession) -> dict[str, int]:
        return {
            "carts": int(await session.scalar(select(func.count()).select_from(Cart)) or 0),
            "items": int(await session.scalar(select(func.count()).select_from(CartItem)) or 0),
            "migration_runs": int(
                await session.scalar(select(func.count()).select_from(CartMigrationRun)) or 0
            ),
        }
