from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product


@dataclass(frozen=True, slots=True)
class CdekQuoteProduct:
    product_id: int
    is_active: bool
    weight_kg: Decimal
    height_cm: Decimal
    width_cm: Decimal
    length_cm: Decimal


class CdekQuoteRepository:
    async def list_products(
        self,
        session: AsyncSession,
        product_ids: set[int],
    ) -> list[CdekQuoteProduct]:
        if not product_ids:
            return []
        rows = (
            await session.execute(
                select(
                    Product.id,
                    Product.is_active,
                    Product.weight_kg,
                    Product.height_cm,
                    Product.width_cm,
                    Product.length_cm,
                )
                .where(Product.id.in_(product_ids))
                .order_by(Product.id)
            )
        ).all()
        return [
            CdekQuoteProduct(
                product_id=row.id,
                is_active=row.is_active,
                weight_kg=row.weight_kg,
                height_cm=row.height_cm,
                width_cm=row.width_cm,
                length_cm=row.length_cm,
            )
            for row in rows
        ]
