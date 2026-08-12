from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import CatalogAuditEvent, Product, ProductVariant
from app.modules.media.models import ProductMedia, ProductVariantMedia


class CatalogRepository:
    async def list_products(self, session: AsyncSession) -> list[Product]:
        result = await session.scalars(
            select(Product)
            .options(selectinload(Product.media_links).selectinload(ProductMedia.media))
            .order_by(Product.id.desc())
        )
        return list(result.unique())

    async def get_product(
        self,
        session: AsyncSession,
        product_id: int,
    ) -> Product | None:
        return await session.scalar(
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.media_links).selectinload(ProductMedia.media),
                selectinload(Product.variants)
                .selectinload(ProductVariant.media_links)
                .selectinload(ProductVariantMedia.media),
            )
        )

    async def get_product_for_update(
        self,
        session: AsyncSession,
        product_id: int,
    ) -> Product | None:
        return await session.scalar(
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.media_links).selectinload(ProductMedia.media),
                selectinload(Product.variants)
                .selectinload(ProductVariant.media_links)
                .selectinload(ProductVariantMedia.media),
            )
            .with_for_update()
        )

    async def get_variant_for_update(
        self,
        session: AsyncSession,
        variant_id: int,
    ) -> ProductVariant | None:
        return await session.scalar(
            select(ProductVariant)
            .where(ProductVariant.id == variant_id)
            .options(
                selectinload(ProductVariant.media_links).selectinload(ProductVariantMedia.media)
            )
            .with_for_update()
        )

    async def list_variants(
        self,
        session: AsyncSession,
        product_id: int,
    ) -> list[ProductVariant]:
        return list(
            await session.scalars(
                select(ProductVariant)
                .where(ProductVariant.product_id == product_id)
                .options(
                    selectinload(ProductVariant.media_links).selectinload(ProductVariantMedia.media)
                )
                .order_by(ProductVariant.id)
            )
        )

    async def get_order_products_for_update(
        self,
        session: AsyncSession,
        product_ids: set[int],
    ) -> list[Product]:
        if not product_ids:
            return []
        products = list(
            await session.scalars(
                select(Product)
                .where(Product.id.in_(product_ids))
                .options(selectinload(Product.variants))
                .order_by(Product.id)
                .with_for_update()
            )
        )
        list(
            await session.scalars(
                select(ProductVariant)
                .where(ProductVariant.product_id.in_(product_ids))
                .order_by(ProductVariant.product_id, ProductVariant.id)
                .with_for_update()
            )
        )
        return products

    @staticmethod
    async def add_product(session: AsyncSession, product: Product) -> None:
        session.add(product)
        await session.flush()

    @staticmethod
    async def delete_product(session: AsyncSession, product: Product) -> None:
        await session.delete(product)
        await session.flush()

    @staticmethod
    async def add_audit_event(
        session: AsyncSession,
        *,
        action: str,
        product_id: int,
        actor_user_id: int,
        snapshot_checksum_sha256: str,
        details: dict[str, object],
    ) -> None:
        session.add(
            CatalogAuditEvent(
                action=action,
                product_id=product_id,
                actor_user_id=actor_user_id,
                snapshot_checksum_sha256=snapshot_checksum_sha256,
                details=details,
            )
        )
        await session.flush()

    @staticmethod
    async def clear_product_children(session: AsyncSession, product: Product) -> None:
        product.variants.clear()
        product.media_links.clear()
        await session.flush()

    @staticmethod
    async def clear_variant_media(
        session: AsyncSession,
        variant: ProductVariant,
    ) -> None:
        variant.media_links.clear()
        await session.flush()
