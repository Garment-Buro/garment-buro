from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload, selectinload

from app.db.text import UnicodeLower, unicode_contains
from app.modules.catalog.admin_schemas import CatalogAdminQuery
from app.modules.catalog.models import Product, ProductCategory, ProductVariant
from app.modules.catalog.storefront_repository import string_values
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement
from app.modules.crm.material_models import CrmMaterialBalance
from app.modules.crm.reference_models import CrmFabric, CrmGarmentModel
from app.modules.media.models import ProductMedia
from app.modules.partners.models import PartnerLanding, PartnerLandingProduct


def product_capacity():
    """SQL equivalent of availability.load_availability, without loading all SKUs.

    A fabric appears once per model, regardless of how many sizes use it. Missing
    fabric references count only for single-fabric models, matching checkout.
    """
    requirement = CrmGarmentFabricRequirement
    cost = (
        func.ceil(requirement.meters_per_unit * (1 + requirement.waste_percent / 100) * 1000) / 1000
    )
    meters = func.coalesce(
        CrmMaterialBalance.on_hand_meters - CrmMaterialBalance.reserved_meters, 0
    )
    fabrics = (
        select(
            requirement.garment_model_id.label("model_id"),
            requirement.fabric_id,
            func.floor(case((meters > 0, meters), else_=0) / cost)
            .cast(BigInteger)
            .label("capacity"),
            func.count().over(partition_by=requirement.garment_model_id).label("fabric_count"),
        )
        .join(CrmFabric, CrmFabric.id == requirement.fabric_id)
        .join(CrmGarmentModel, CrmGarmentModel.id == requirement.garment_model_id)
        .outerjoin(CrmMaterialBalance, CrmMaterialBalance.fabric_id == requirement.fabric_id)
        .where(CrmFabric.is_active.is_(True), CrmGarmentModel.is_active.is_(True))
        .cte("catalog_fabric_capacity")
    )
    used_by_variant = (
        select(1)
        .select_from(ProductVariant)
        .where(
            ProductVariant.product_id == Product.id,
            or_(
                ProductVariant.fabric_id == fabrics.c.fabric_id,
                and_(ProductVariant.fabric_id.is_(None), fabrics.c.fabric_count == 1),
            ),
        )
        .correlate(Product, fabrics)
        .exists()
    )
    has_variants = (
        select(1).where(ProductVariant.product_id == Product.id).correlate(Product).exists()
    )
    capacity = (
        select(func.coalesce(func.sum(fabrics.c.capacity), 0))
        .where(
            fabrics.c.model_id == Product.garment_model_id,
            or_(used_by_variant, and_(~has_variants, fabrics.c.fabric_count == 1)),
        )
        .correlate(Product)
        .scalar_subquery()
    )
    return case(
        (Product.garment_model_id.is_(None), Product.stock_quantity - Product.reserved_quantity),
        else_=capacity,
    )


class CatalogAdminRepository:
    @staticmethod
    async def community_previews(session: AsyncSession, product_ids: list[int]):
        if not product_ids:
            return {}
        ranked = (
            select(
                PartnerLandingProduct.product_id,
                PartnerLanding.id,
                PartnerLanding.title,
                PartnerLanding.slug,
                func.count().over(partition_by=PartnerLandingProduct.product_id).label("total"),
                func.row_number()
                .over(
                    partition_by=PartnerLandingProduct.product_id,
                    order_by=PartnerLanding.id.desc(),
                )
                .label("position"),
            )
            .join(PartnerLanding, PartnerLanding.id == PartnerLandingProduct.landing_id)
            .where(PartnerLandingProduct.product_id.in_(product_ids))
            .subquery()
        )
        rows = (
            await session.execute(
                select(ranked)
                .where(ranked.c.position <= 3)
                .order_by(ranked.c.product_id, ranked.c.position)
            )
        ).mappings()
        result = {}
        for row in rows:
            result.setdefault(row["product_id"], []).append(row)
        return result

    @staticmethod
    async def counts(session: AsyncSession) -> dict[str, int]:
        rows = await session.execute(
            select(Product.preset_source, func.count())
            .where(Product.is_demo.is_(False))
            .group_by(Product.preset_source)
        )
        return {source: count for source, count in rows}

    @staticmethod
    async def list_page(
        session: AsyncSession,
        query: CatalogAdminQuery,
        *,
        after_id: int | None,
        after_value: str | Decimal | int | None,
    ):
        field, direction = query.sort.split(":")
        ascending = direction == "asc"
        capacity = product_capacity()
        stock = capacity if query.stock != "all" or field == "stock" else None
        variant_count = (
            select(func.count())
            .where(ProductVariant.product_id == Product.id)
            .correlate(Product)
            .scalar_subquery()
        )
        title = UnicodeLower(Product.title)
        if session.get_bind().dialect.name == "postgresql":
            title = title.collate("C")
        order_value = {
            "id": Product.id,
            "title": title,
            "price": Product.price,
            "stock": stock,
            "variants": variant_count,
        }[field]
        statement = (
            select(
                Product,
                order_value.label("order_value"),
                ProductCategory.name.label("category_name"),
                CrmGarmentModel.name.label("garment_model_name"),
                capacity.label("available_quantity"),
                variant_count.label("variant_count"),
                select(ProductVariant.sku)
                .where(
                    ProductVariant.product_id == Product.id,
                    ProductVariant.sku.is_not(None),
                    ProductVariant.sku != "",
                )
                .order_by(ProductVariant.id)
                .limit(1)
                .correlate(Product)
                .scalar_subquery()
                .label("sku"),
            )
            .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
            .outerjoin(CrmGarmentModel, CrmGarmentModel.id == Product.garment_model_id)
            .where(Product.is_demo.is_(False))
        )
        if query.garment_model_id is not None:
            statement = statement.where(Product.garment_model_id == query.garment_model_id)
        if query.category_id is not None:
            statement = statement.where(Product.category_id == query.category_id)
        if query.active is not None:
            statement = statement.where(Product.is_active.is_(query.active))
        if query.source != "all":
            statement = statement.where(Product.preset_source == query.source)
        if query.community_id is not None:
            statement = statement.where(
                select(1)
                .where(
                    PartnerLandingProduct.product_id == Product.id,
                    PartnerLandingProduct.landing_id == query.community_id,
                )
                .exists()
            )
        if query.stock != "all":
            statement = statement.where(stock > 0 if query.stock == "available" else stock <= 0)
        if query.query:
            tags = string_values(session, Product.tags, "admin_search_tags")
            statement = statement.where(
                or_(
                    unicode_contains(Product.title, query.query),
                    unicode_contains(Product.slug, query.query),
                    select(1)
                    .select_from(tags)
                    .where(unicode_contains(tags.c.value, query.query))
                    .exists(),
                )
            )
        if after_id is not None:
            value_after = order_value > after_value if ascending else order_value < after_value
            id_after = Product.id > after_id if ascending else Product.id < after_id
            statement = statement.where(
                or_(value_after, and_(order_value == after_value, id_after))
            )
        result = await session.execute(
            statement.order_by(
                order_value.asc() if ascending else order_value.desc(),
                Product.id.asc() if ascending else Product.id.desc(),
            )
            .limit(query.limit + 1)
            .options(
                raiseload(Product.variants),
                selectinload(Product.media_links).selectinload(ProductMedia.media),
            )
        )
        return list(result)
