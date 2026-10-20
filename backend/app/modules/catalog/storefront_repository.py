from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, cast, column, func, or_, select, true, tuple_, union_all, values
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import unicode_contains
from app.modules.catalog.models import Product, ProductCategory
from app.modules.catalog.public_policy import public_product_conditions, public_product_ids
from app.modules.catalog.storefront_schemas import StorefrontQuery
from app.modules.media.models import MediaObject, MediaStatus, ProductMedia, ProductMediaRole

CARD_IMAGE_ROLES = (
    ProductMediaRole.MOBILE_CARD_IMAGE.value,
    ProductMediaRole.DESKTOP_CARD_IMAGES.value,
    ProductMediaRole.IMAGE_LEFT.value,
    ProductMediaRole.GALLERY_IMAGES.value,
    ProductMediaRole.MOBILE_SLIDER_IMAGES.value,
)

COLLECTION_IMAGE_ROLES = (
    ProductMediaRole.DESKTOP_VIDEO_POSTER.value,
    ProductMediaRole.MOBILE_VIDEO_POSTER.value,
    ProductMediaRole.MOBILE_CARD_IMAGE.value,
    ProductMediaRole.IMAGE_LEFT.value,
)


def string_values(session: AsyncSession, column, name: str):
    """Database-side expansion of a string array, never loading products in Python."""
    if session.get_bind().dialect.name == "postgresql":
        return func.jsonb_array_elements_text(cast(column, JSONB)).table_valued("value").alias(name)
    return func.json_each(column).table_valued("value").alias(name)


class StorefrontRepository:
    async def public_price(self, session: AsyncSession, product_id: int) -> Decimal | None:
        return await session.scalar(
            select(Product.price).where(
                Product.id == product_id, Product.id.in_(public_product_ids())
            )
        )

    async def list_page(
        self,
        session: AsyncSession,
        *,
        query: StorefrontQuery,
        after_id: int | None,
        after_price: Decimal | None,
        after_created_at: datetime | None,
    ) -> list[Mapping[str, Any]]:
        statement = (
            select(
                Product.id,
                Product.created_at.label("_created_at"),
                Product.title,
                Product.price,
                Product.colors,
                Product.tags,
                Product.preset_source.label("source"),
                Product.category_id,
                ProductCategory.name.label("category_name"),
            )
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .where(*public_product_conditions())
        )
        if query.ids:
            statement = statement.where(Product.id.in_(query.ids))
        if query.category_ids:
            statement = statement.where(Product.category_id.in_(query.category_ids))
        if query.source:
            statement = statement.where(Product.preset_source == query.source)
        if query.min_price is not None:
            statement = statement.where(Product.price >= query.min_price)
        if query.max_price is not None:
            statement = statement.where(Product.price <= query.max_price)
        if query.colors:
            colors = string_values(session, Product.colors, "filter_colors")
            statement = statement.where(
                select(1).select_from(colors).where(colors.c.value.in_(query.colors)).exists()
            )
        if query.query.strip():
            tags = string_values(session, Product.tags, "search_tags")
            statement = statement.where(
                or_(
                    unicode_contains(Product.title, query.query.strip()),
                    select(1)
                    .select_from(tags)
                    .where(unicode_contains(tags.c.value, query.query.strip()))
                    .exists(),
                )
            )
        if query.sort in ("cheap", "expensive"):
            ascending = query.sort == "cheap"
            ordering = (
                Product.price.asc() if ascending else Product.price.desc(),
                Product.id.desc(),
            )
            if after_id is not None and ascending:
                # Opposite sort directions cannot use a single row comparison.
                # Seek the rest of this price and the higher prices separately,
                # bounded before merging. Both inherit every publication/filter rule.
                same_price = (
                    statement.where(
                        # Keep the leading price in ORDER BY: equality otherwise
                        # lets PostgreSQL prefer the PK and filter earlier prices.
                        Product.price.between(after_price, after_price),
                        Product.id < after_id,
                    )
                    .order_by(*ordering)
                    .limit(query.limit + 1)
                    .subquery()
                )
                higher_prices = (
                    statement.where(Product.price > after_price)
                    .order_by(*ordering)
                    .limit(query.limit + 1)
                    .subquery()
                )
                candidates = union_all(select(same_price), select(higher_prices)).subquery()
                statement = select(candidates).order_by(
                    candidates.c.price.asc(), candidates.c.id.desc()
                )
            else:
                if after_id is not None:
                    statement = statement.where(
                        tuple_(Product.price, Product.id) < tuple_(after_price, after_id)
                    )
                statement = statement.order_by(*ordering)
        else:
            ascending = query.sort == "oldest"
            created = Product.created_at
            after_created = after_created_at
            if session.get_bind().dialect.name == "sqlite":
                # SQLite mixes CURRENT_TIMESTAMP text and DateTime-bound text formats.
                # Its date function gives both a consistent comparison/order value.
                created = func.julianday(Product.created_at)
                after_created = func.julianday(after_created_at) if after_created_at else None
            if after_id is not None:
                key, after = tuple_(created, Product.id), tuple_(after_created, after_id)
                statement = statement.where(key > after if ascending else key < after)
            statement = statement.order_by(
                created.asc() if ascending else created.desc(),
                Product.id.asc() if ascending else Product.id.desc(),
            )
        result = await session.execute(statement.limit(query.limit + 1))
        return list(result.mappings())

    async def collection_products(
        self, session: AsyncSession, product_ids: list[int]
    ) -> list[Mapping[str, Any]]:
        result = await session.execute(
            select(Product.id, Product.title, Product.price, Product.description)
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .where(Product.id.in_(product_ids), *public_product_conditions())
            .limit(len(product_ids))
        )
        return list(result.mappings())

    @staticmethod
    def card_images_statement(
        product_ids: list[int],
        *,
        roles: tuple[str, ...] = CARD_IMAGE_ROLES,
        dialect_name: str = "postgresql",
    ):
        owners = (
            values(column("product_id", Integer))
            .data([(product_id,) for product_id in dict.fromkeys(product_ids)])
            .cte("card_image_owners")
        )
        # A scalar point lookup prevents a semi/hash join from scanning the global
        # registry. Hidden/non-image prefixes are still searched, never truncated.
        eligible = (
            select(MediaObject.id)
            .where(
                MediaObject.id == ProductMedia.media_object_id,
                MediaObject.status == MediaStatus.READY.value,
                MediaObject.is_public.is_(True),
                MediaObject.content_type.startswith("image/"),
            )
            .correlate(ProductMedia)
            .limit(1)
            .scalar_subquery()
        )
        candidates = [
            select(ProductMedia.id)
            .where(
                ProductMedia.product_id == owners.c.product_id,
                ProductMedia.role == role,
                eligible.is_not(None),
            )
            # UNIQUE(owner,role,sort_order) makes an additional id tie-break redundant.
            .order_by(ProductMedia.sort_order)
            .limit(1)
            .correlate(owners)
            .scalar_subquery()
            for role in roles
        ]
        # COALESCE short-circuits: lower-priority roles are not read after a match.
        choice = candidates[0] if len(candidates) == 1 else func.coalesce(*candidates)
        chosen = (
            select(owners.c.product_id, choice.label("link_id"))
            .cte("card_image_choices")
            .prefix_with("MATERIALIZED", dialect="postgresql")
        )
        if dialect_name == "postgresql":
            link = (
                select(ProductMedia.alt_text, ProductMedia.media_object_id)
                .where(ProductMedia.id == chosen.c.link_id)
                .correlate(chosen)
                .limit(1)
                .lateral("card_image_link")
            )
            media = (
                select(MediaObject.bucket_name, MediaObject.object_key)
                .where(MediaObject.id == link.c.media_object_id)
                .correlate(link)
                .limit(1)
                .lateral("card_image_object")
            )
            return select(
                chosen.c.product_id, link.c.alt_text, media.c.bucket_name, media.c.object_key
            ).select_from(chosen.join(link, true()).join(media, true()))
        # SQLite is the lightweight contract dialect, without LATERAL support.
        return (
            select(
                chosen.c.product_id,
                ProductMedia.alt_text,
                MediaObject.bucket_name,
                MediaObject.object_key,
            )
            .select_from(chosen)
            .join(ProductMedia, ProductMedia.id == chosen.c.link_id)
            .join(MediaObject, MediaObject.id == ProductMedia.media_object_id)
        )

    async def card_images(
        self,
        session: AsyncSession,
        product_ids: list[int],
        *,
        roles: tuple[str, ...] = CARD_IMAGE_ROLES,
    ):
        if not product_ids or not roles:
            return {}
        result = await session.execute(
            self.card_images_statement(
                product_ids, roles=roles, dialect_name=session.get_bind().dialect.name
            )
        )
        return {row["product_id"]: row for row in result.mappings()}

    async def options(self, session: AsyncSession):
        categories = await session.execute(
            select(ProductCategory.id, ProductCategory.name)
            .where(
                ProductCategory.is_active.is_(True),
                select(1)
                .select_from(Product)
                .where(
                    Product.category_id == ProductCategory.id,
                    *public_product_conditions(),
                )
                .correlate(ProductCategory)
                .exists(),
            )
            .order_by(ProductCategory.name, ProductCategory.id)
        )
        # Global choices still read public products. Deduplicate their palettes
        # before expansion, so shared colors do not multiply per product.
        palettes = (
            select(Product.colors)
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .where(*public_product_conditions())
            .distinct()
            .subquery("public_palettes")
        )
        values = string_values(session, palettes.c.colors, "option_colors")
        colors = await session.scalars(
            select(values.c.value)
            .select_from(palettes)
            .join(values, true())
            .distinct()
            .order_by(values.c.value)
        )
        return list(categories.mappings()), list(colors)
