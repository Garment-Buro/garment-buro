"""Read a complete editable preset without hydrating an oversized SKU collection."""

from dataclasses import dataclass

from sqlalchemy import select, true, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, raiseload

from app.core.config import Settings
from app.modules.catalog.editor_media import CatalogEditorMediaBudget
from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.schemas import CATALOG_EDITOR_VARIANT_LIMIT
from app.modules.media.models import MediaObject, ProductMedia, ProductVariantMedia
from app.modules.media.read_models import CatalogMediaLinkView, CatalogMediaView

EDITOR_MEDIA_PAGE_SIZE = 256


class CatalogEditorVariantLimitError(ValueError):
    pass


def catalog_editor_variant_limit_detail() -> dict[str, str]:
    return {
        "code": "catalog_editor_variant_limit",
        "message": (
            f"В пресете больше {CATALOG_EDITOR_VARIANT_LIMIT} вариантов. "
            "Открыть весь состав в редакторе пока нельзя."
        ),
    }


@dataclass
class CatalogEditorSnapshot:
    product: Product
    variants: list[ProductVariant]
    media_links: list[CatalogMediaLinkView]
    variant_media: dict[int, list[CatalogMediaLinkView]]


class CatalogEditorRepository:
    @staticmethod
    def variant_statement(product_id: int, *, dialect_name: str = "postgresql"):
        ids = (
            select(ProductVariant.id)
            # A closed owner range keeps both columns in the ordered key. Equality
            # lets PostgreSQL discard the owner pathkey and choose a global PK scan
            # with thousands of owner-filtered rows before LIMIT.
            .where(ProductVariant.product_id.between(product_id, product_id))
            .order_by(ProductVariant.product_id, ProductVariant.id)
            .limit(CATALOG_EDITOR_VARIANT_LIMIT + 1)
            .cte("editor_variant_ids")
            .prefix_with("MATERIALIZED", dialect="postgresql")
        )
        if dialect_name == "postgresql":
            point = (
                select(ProductVariant)
                .where(ProductVariant.id == ids.c.id)
                .correlate(ids)
                .limit(1)
                .lateral("editor_variant")
            )
            entity = aliased(ProductVariant, point)
            statement = select(entity).select_from(ids.join(point, true()))
        else:
            statement = select(ProductVariant).join(ids, ProductVariant.id == ids.c.id)
        return (
            statement.order_by(ids.c.id)
            .options(raiseload("*"))
            .execution_options(populate_existing=True)
        )

    @classmethod
    async def variants(cls, session: AsyncSession, product_id: int) -> list[ProductVariant]:
        variants = list(
            await session.scalars(
                cls.variant_statement(product_id, dialect_name=session.get_bind().dialect.name)
            )
        )
        if len(variants) > CATALOG_EDITOR_VARIANT_LIMIT:
            raise CatalogEditorVariantLimitError
        return variants

    @classmethod
    async def detail(
        cls, session: AsyncSession, product_id: int, *, settings: Settings
    ) -> CatalogEditorSnapshot | None:
        product = await session.scalar(
            select(Product)
            .where(Product.id == product_id)
            .options(raiseload("*"))
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        if product is None:
            return None
        variants = await cls.variants(session, product_id)
        return await cls.media_snapshot(session, product, variants, settings=settings)

    @classmethod
    async def media_snapshot(
        cls,
        session: AsyncSession,
        product: Product,
        variants: list[ProductVariant],
        *,
        settings: Settings,
    ) -> CatalogEditorSnapshot:
        """Read a complete bounded source, or fail before building an uneditable DTO."""
        budget = CatalogEditorMediaBudget(settings)
        media_links = []
        async for link in cls.media_links(session, product_id=product.id):
            budget.accept(link, variant=False)
            media_links.append(link)
        variant_media: dict[int, list[CatalogMediaLinkView]] = {row.id: [] for row in variants}
        if variant_media:
            async for link in cls.media_links(session, variant_ids=list(variant_media)):
                budget.accept(link, variant=True)
                variant_media[link.owner_id].append(link)
        # Keep source relationships unloaded: this is a DTO source, never a partial ORM aggregate.
        return CatalogEditorSnapshot(product, variants, media_links, variant_media)

    @staticmethod
    def media_page_statement(
        *,
        product_id: int | None = None,
        variant_ids: list[int] | None = None,
        after: tuple | None = None,
        dialect_name: str = "postgresql",
    ):
        variant = product_id is None
        model = ProductVariantMedia if variant else ProductMedia
        owner = model.product_variant_id if variant else model.product_id
        ordering = (
            [owner, model.role, model.sort_order] if variant else [model.role, model.sort_order]
        )
        page = select(
            model.id, owner.label("owner_id"), model.role, model.sort_order, model.media_object_id
        )
        page = page.where(owner.in_(variant_ids) if variant else owner == product_id)
        if after is not None:
            page = page.where(tuple_(*ordering) > tuple_(*after))
        # Bound candidates before joining the global media registry. Existing unique
        # (owner, role, sort_order) keys also provide stable keyset ordering.
        page = (
            page.order_by(*ordering)
            .limit(EDITOR_MEDIA_PAGE_SIZE + 1)
            .cte("editor_media_page")
            .prefix_with("MATERIALIZED", dialect="postgresql")
        )
        order = (
            [page.c.owner_id, page.c.role, page.c.sort_order]
            if variant
            else [page.c.role, page.c.sort_order]
        )
        metadata = [
            MediaObject.id.label("media_id"),
            MediaObject.bucket_name,
            MediaObject.object_key,
            MediaObject.content_type,
            MediaObject.status,
            MediaObject.is_public,
        ]
        if dialect_name == "postgresql":
            # An ordinary join can scan the whole global registry (hash/merge join)
            # even though candidates are bounded. Keep each metadata lookup a PK point.
            media = (
                select(*metadata)
                .where(MediaObject.id == page.c.media_object_id)
                .correlate(page)
                .limit(1)
                .lateral("editor_media_object")
            )
            return select(page, *media.c).select_from(page.join(media, true())).order_by(*order)
        # SQLite is the contract-test dialect and has no LATERAL support.
        return (
            select(page, *metadata)
            .join(MediaObject, MediaObject.id == page.c.media_object_id)
            .order_by(*order)
        )

    @classmethod
    async def media_page(cls, session: AsyncSession, **query):
        return (
            (
                await session.execute(
                    cls.media_page_statement(**query, dialect_name=session.get_bind().dialect.name)
                )
            )
            .mappings()
            .all()
        )

    @classmethod
    async def media_links(
        cls,
        session: AsyncSession,
        *,
        product_id: int | None = None,
        variant_ids: list[int] | None = None,
    ):
        after = None
        while True:
            rows = await cls.media_page(
                session, product_id=product_id, variant_ids=variant_ids, after=after
            )
            for row in rows[:EDITOR_MEDIA_PAGE_SIZE]:
                yield CatalogMediaLinkView(
                    id=row.id,
                    owner_id=row.owner_id,
                    role=row.role,
                    sort_order=row.sort_order,
                    media=CatalogMediaView(
                        id=row.media_id,
                        bucket_name=row.bucket_name,
                        object_key=row.object_key,
                        content_type=row.content_type,
                        status=row.status,
                        is_public=row.is_public,
                    ),
                )
            if len(rows) <= EDITOR_MEDIA_PAGE_SIZE:
                return
            last = rows[EDITOR_MEDIA_PAGE_SIZE - 1]
            after = (
                (last.owner_id, last.role, last.sort_order)
                if product_id is None
                else (last.role, last.sort_order)
            )
