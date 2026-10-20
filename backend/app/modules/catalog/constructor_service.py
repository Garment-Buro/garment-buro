"""One public asset registry and ordered image references for the constructor."""

from urllib.parse import quote

from app.core.config import Settings
from app.modules.catalog.availability import available_stock, load_availability
from app.modules.catalog.constructor_repository import ConstructorRepository
from app.modules.catalog.constructor_schemas import (
    ConstructorImage,
    ConstructorMedia,
    ConstructorProductResponse,
    ConstructorVariant,
)
from app.modules.media.urls import public_media_url


class ConstructorService:
    def __init__(self, settings: Settings, repository: ConstructorRepository | None = None):
        self.settings = settings
        self.repository = repository or ConstructorRepository()

    async def get_product(self, session, product_id: int) -> ConstructorProductResponse | None:
        product = await self.repository.product(session, product_id)
        if product is None:
            return None
        variants = await self.repository.variants(session, product_id)
        await load_availability(session, [product], variants_by_product={product.id: variants})
        media = {}

        def image(row):
            if row.media_id not in media:
                # public_media_url only needs these storage identity fields.
                media[row.media_id] = ConstructorMedia(
                    id=row.media_id,
                    url=(
                        "/" + quote(row.object_key, safe="/")
                        if row.object_key.startswith("uploads/")
                        else public_media_url(self.settings, row)
                    ),
                    content_type=row.content_type,
                )
            return ConstructorImage(media_id=row.media_id, role=row.role, sort_order=row.sort_order)

        images = [
            image(row) for row in await self.repository.images(session, product_id, variants=False)
        ]
        variant_images = {variant.id: [] for variant in variants}
        if variants:
            for row in await self.repository.images(session, product_id, variants=True):
                if row.owner_id in variant_images:
                    variant_images[row.owner_id].append(image(row))
        return ConstructorProductResponse(
            id=product.id,
            title=product.title,
            price=float(product.price),
            stock_quantity=available_stock(product),
            sizes=product.sizes,
            images=images,
            variants=[
                ConstructorVariant(
                    id=variant.id,
                    size=variant.size,
                    color=variant.color,
                    color_hex=variant.color_hex,
                    stock_quantity=available_stock(variant),
                    width_cm=variant.width_cm,
                    height_cm=variant.height_cm,
                    images=variant_images[variant.id],
                )
                for variant in variants
            ],
            media_assets=sorted(media.values(), key=lambda asset: asset.id),
        )
