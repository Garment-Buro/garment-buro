from __future__ import annotations

from sqlalchemy import literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload, selectinload

from app.modules.catalog.models import (
    CatalogAuditEvent,
    Product,
    ProductCategory,
    ProductVariant,
)
from app.modules.catalog.public_policy import public_product_ids
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement
from app.modules.crm.reference_models import CrmFabric, CrmGarmentModel, CrmGarmentSize
from app.modules.media.models import ProductMedia, ProductVariantMedia


class CatalogRepository:
    @staticmethod
    async def has_fabric_holds(session: AsyncSession, product_id: int) -> bool:
        from app.modules.inventory.models import InventoryFabricHold, InventoryReservation

        return (
            await session.scalar(
                select(InventoryFabricHold.id)
                .join(
                    InventoryReservation,
                    InventoryReservation.id == InventoryFabricHold.reservation_id,
                )
                .where(
                    InventoryReservation.product_id_snapshot == product_id,
                    InventoryFabricHold.remaining_meters > 0,
                )
                .limit(1)
            )
            is not None
        )

    @staticmethod
    async def get_category(
        session: AsyncSession,
        category_id: int,
        *,
        lock: bool = False,
    ) -> ProductCategory | None:
        statement = select(ProductCategory).where(ProductCategory.id == category_id)
        return await session.scalar(
            statement.with_for_update().execution_options(populate_existing=True)
            if lock
            else statement
        )

    @staticmethod
    async def add_category(session: AsyncSession, category: ProductCategory) -> None:
        session.add(category)
        await session.flush()

    @staticmethod
    async def garment_model_exists(session: AsyncSession, garment_model_id: int) -> bool:
        return (
            await session.scalar(
                select(CrmGarmentModel.id).where(
                    CrmGarmentModel.id == garment_model_id,
                    CrmGarmentModel.is_active.is_(True),
                )
            )
            is not None
        )

    @staticmethod
    async def active_category_exists(session: AsyncSession, category_id: int) -> bool:
        return (
            await session.scalar(
                select(ProductCategory.id).where(
                    ProductCategory.id == category_id, ProductCategory.is_active.is_(True)
                )
            )
            is not None
        )

    @staticmethod
    async def active_size_codes(
        session: AsyncSession, *, garment_model_id: int, size_ids: set[int]
    ) -> dict[int, str]:
        if not size_ids:
            return {}
        rows = await session.execute(
            select(CrmGarmentSize.id, CrmGarmentSize.code).where(
                CrmGarmentSize.id.in_(size_ids),
                CrmGarmentSize.garment_model_id == garment_model_id,
                CrmGarmentSize.is_active.is_(True),
            )
        )
        return dict(rows.tuples().all())

    @staticmethod
    async def allowed_active_fabric_ids(
        session: AsyncSession,
        *,
        garment_model_id: int,
        fabric_ids: set[int],
    ) -> set[int]:
        if not fabric_ids:
            return set()
        return set(
            await session.scalars(
                select(CrmFabric.id)
                .join(
                    CrmGarmentFabricRequirement,
                    CrmGarmentFabricRequirement.fabric_id == CrmFabric.id,
                )
                .where(
                    CrmGarmentFabricRequirement.garment_model_id == garment_model_id,
                    CrmFabric.id.in_(fabric_ids),
                    CrmFabric.is_active.is_(True),
                )
            )
        )

    async def list_products(self, session: AsyncSession) -> list[Product]:
        result = await session.scalars(
            select(Product)
            .options(
                selectinload(Product.media_links).selectinload(ProductMedia.media),
                selectinload(Product.variants),
            )
            .order_by(Product.id.desc())
        )
        return list(result.unique())

    async def get_product(
        self,
        session: AsyncSession,
        product_id: int,
        *,
        public_only: bool = False,
    ) -> Product | None:
        return await session.scalar(
            select(Product)
            .where(
                Product.id == product_id,
                *([Product.id.in_(public_product_ids())] if public_only else []),
            )
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
            .options(raiseload("*"))
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    @staticmethod
    def reserved_variant_statement(product_id: int):
        # Literal zero keeps the partial index applicable to PostgreSQL generic plans.
        return (
            select(ProductVariant.id)
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.reserved_quantity > literal_column("0"),
            )
            .order_by(ProductVariant.id)
            .limit(1)
        )

    @classmethod
    async def has_reserved_variants(cls, session: AsyncSession, product_id: int) -> bool:
        return await session.scalar(cls.reserved_variant_statement(product_id)) is not None

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
