"""Scalar cursor reads for deletion evidence; no product aggregate is hydrated."""

from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import ProductVariant
from app.modules.media.models import MediaObject, ProductMedia, ProductVariantMedia

DELETION_AUDIT_BATCH_SIZE = 256


class CatalogDeletionRepository:
    @staticmethod
    def sections(product_id: int):
        media_columns = [
            column.label("media_" + column.name) for column in MediaObject.__table__.columns
        ]
        return {
            "variants": select(*ProductVariant.__table__.columns)
            .where(ProductVariant.product_id == product_id)
            .order_by(ProductVariant.id),
            "product_media": select(*ProductMedia.__table__.columns, *media_columns)
            .join(MediaObject, MediaObject.id == ProductMedia.media_object_id)
            .where(ProductMedia.product_id == product_id)
            .order_by(ProductMedia.id),
            "variant_media": select(*ProductVariantMedia.__table__.columns, *media_columns)
            .join(MediaObject, MediaObject.id == ProductVariantMedia.media_object_id)
            .join(ProductVariant, ProductVariant.id == ProductVariantMedia.product_variant_id)
            .where(ProductVariant.product_id == product_id)
            .order_by(ProductVariantMedia.product_variant_id, ProductVariantMedia.id),
        }

    @staticmethod
    async def rows(session: AsyncSession, statement) -> AsyncIterator[dict[str, object]]:
        result = await session.stream(
            statement.execution_options(yield_per=DELETION_AUDIT_BATCH_SIZE)
        )
        try:
            async for batch in result.mappings().partitions(DELETION_AUDIT_BATCH_SIZE):
                for row in batch:
                    yield dict(row)
        finally:
            await result.close()
