"""Replace owned media links without reading the previous media collection."""

from collections.abc import Iterable
from itertools import islice

from sqlalchemy import delete, insert, inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.models import MediaObject, ProductMedia, ProductVariantMedia

MEDIA_WRITE_BATCH_SIZE = 256


class CatalogEditorCommands:
    @staticmethod
    async def clear_media(session: AsyncSession, *, product_id: int, variant_ids: set[int]) -> None:
        # The caller holds the parent lock and has read the complete, <=200-SKU source.
        # Core DELETE avoids RETURNING/hydrating an arbitrarily large old link set.
        await session.execute(
            delete(ProductMedia.__table__).where(ProductMedia.product_id == product_id)
        )
        if variant_ids:
            await session.execute(
                delete(ProductVariantMedia.__table__).where(
                    ProductVariantMedia.product_variant_id.in_(variant_ids)
                )
            )
        # A previous reader may have populated this request's identity map. Discard only
        # cached deleted links, without fetching expired attributes or old collections.
        removed = []
        for row in list(session.identity_map.values()):
            state = inspect(row)
            if (isinstance(row, ProductMedia) and state.dict.get("product_id") == product_id) or (
                isinstance(row, ProductVariantMedia)
                and state.dict.get("product_variant_id") in variant_ids
            ):
                removed.append(row)
        removed_ids = {id(row) for row in removed}
        for row in list(session.identity_map.values()):
            if isinstance(row, MediaObject):
                for name in ("product_links", "variant_links"):
                    cached = inspect(row).dict.get(name)
                    if cached is not None and any(id(link) in removed_ids for link in cached):
                        session.expire(row, [name])
        for row in removed:
            session.expunge(row)

    @staticmethod
    async def add_media(
        session: AsyncSession,
        model: type[ProductMedia] | type[ProductVariantMedia],
        rows: Iterable[dict[str, object]],
    ) -> None:
        iterator = iter(rows)
        while batch := list(islice(iterator, MEDIA_WRITE_BATCH_SIZE)):
            await session.execute(insert(model.__table__), batch)
