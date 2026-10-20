"""Load the public constructor source without an editable ORM aggregate."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, raiseload

from app.modules.catalog.models import Product, ProductCategory, ProductVariant
from app.modules.catalog.public_policy import public_product_conditions
from app.modules.media.models import MediaObject, MediaStatus, ProductMedia, ProductVariantMedia

CONSTRUCTOR_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")


class ConstructorRepository:
    async def product(self, session: AsyncSession, product_id: int) -> Product | None:
        return await session.scalar(
            select(Product)
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .where(Product.id == product_id, *public_product_conditions())
            .options(
                load_only(
                    Product.id,
                    Product.title,
                    Product.price,
                    Product.sizes,
                    Product.stock_quantity,
                    Product.reserved_quantity,
                    Product.garment_model_id,
                    raiseload=True,
                ),
                raiseload("*"),
            )
        )

    async def variants(self, session: AsyncSession, product_id: int) -> list[ProductVariant]:
        return list(
            await session.scalars(
                select(ProductVariant)
                .where(ProductVariant.product_id == product_id)
                .order_by(ProductVariant.id)
                .options(raiseload("*"))
            )
        )

    async def images(self, session: AsyncSession, product_id: int, *, variants: bool):
        link = ProductVariantMedia if variants else ProductMedia
        owner = link.product_variant_id if variants else link.product_id
        statement = select(
            owner.label("owner_id"),
            link.role,
            link.sort_order,
            MediaObject.id.label("media_id"),
            MediaObject.bucket_name,
            MediaObject.object_key,
            MediaObject.content_type,
        ).join(MediaObject, MediaObject.id == link.media_object_id)
        if variants:
            statement = statement.join(ProductVariant, ProductVariant.id == owner).where(
                ProductVariant.product_id == product_id
            )
        else:
            statement = statement.where(owner == product_id)
        statement = statement.where(
            MediaObject.is_public.is_(True),
            MediaObject.status == MediaStatus.READY.value,
            MediaObject.content_type.in_(CONSTRUCTOR_IMAGE_TYPES),
        ).order_by(owner, link.role, link.sort_order, link.id)
        return (await session.execute(statement)).mappings()
