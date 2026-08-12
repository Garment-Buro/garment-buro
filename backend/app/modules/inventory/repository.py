from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product, ProductVariant
from app.modules.inventory.models import InventoryReservation, InventoryReservationStatus
from app.modules.orders.models import Order


class InventoryRepository:
    @staticmethod
    async def add_reservations(
        session: AsyncSession,
        reservations: list[InventoryReservation],
    ) -> None:
        session.add_all(reservations)
        await session.flush()

    async def list_order_reservations_for_update(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> list[InventoryReservation]:
        return list(
            await session.scalars(
                select(InventoryReservation)
                .where(InventoryReservation.order_id == order_id)
                .order_by(InventoryReservation.id)
                .with_for_update()
            )
        )

    async def lock_stock(
        self,
        session: AsyncSession,
        *,
        product_ids: set[int],
        variant_ids: set[int],
    ) -> tuple[dict[int, Product], dict[int, ProductVariant]]:
        products = list(
            await session.scalars(
                select(Product)
                .where(Product.id.in_(product_ids))
                .order_by(Product.id)
                .with_for_update()
            )
        )
        variants = (
            list(
                await session.scalars(
                    select(ProductVariant)
                    .where(ProductVariant.id.in_(variant_ids))
                    .order_by(ProductVariant.id)
                    .with_for_update()
                )
            )
            if variant_ids
            else []
        )
        return (
            {product.id: product for product in products},
            {variant.id: variant for variant in variants},
        )

    async def list_expired_orders_for_update(
        self,
        session: AsyncSession,
        *,
        now: datetime,
        limit: int,
    ) -> list[Order]:
        expired_order_ids = select(InventoryReservation.order_id).where(
            InventoryReservation.status == InventoryReservationStatus.ACTIVE.value,
            InventoryReservation.expires_at <= now,
        )
        statement = (
            select(Order).where(Order.id.in_(expired_order_ids)).order_by(Order.id).limit(limit)
        )
        if session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        else:
            statement = statement.with_for_update()
        return list(await session.scalars(statement))
