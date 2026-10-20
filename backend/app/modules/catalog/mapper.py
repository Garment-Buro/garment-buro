from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from app.core.config import Settings
from app.modules.catalog.availability import available_stock
from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.schemas import (
    ProductDetailResponse,
    ProductMediaAsset,
    ProductResponse,
    ProductVariantResponse,
)
from app.modules.media.models import (
    MediaObject,
    MediaStatus,
    ProductMedia,
    ProductMediaRole,
    ProductVariantMedia,
    ProductVariantMediaRole,
)
from app.modules.media.read_models import CatalogMediaLinkView, CatalogMediaView
from app.modules.media.urls import public_media_url

PRODUCT_MULTI_MEDIA_ROLES = {
    ProductMediaRole.GALLERY_IMAGES.value,
    ProductMediaRole.DESKTOP_CARD_IMAGES.value,
    ProductMediaRole.DESKTOP_SLIDER_IMAGES.value,
    ProductMediaRole.MOBILE_SLIDER_IMAGES.value,
    ProductMediaRole.MOBILE_PRODUCT_SLIDER_IMAGES.value,
}
VARIANT_MULTI_MEDIA_ROLES = {ProductVariantMediaRole.IMAGES.value}


class CatalogResponseMapper:
    """Map normalized catalog/media rows to the current frontend contract."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def product(self, product: Product) -> ProductResponse:
        return ProductResponse(
            **self._product_scalars(product),
            **self._product_media(product.media_links),
        )

    def product_detail(self, product: Product) -> ProductDetailResponse:
        return self.product_detail_from_parts(
            product,
            product.variants,
            product.media_links,
            {variant.id: variant.media_links for variant in product.variants},
        )

    def product_detail_from_parts(
        self,
        product: Product,
        variants: list[ProductVariant],
        media_links: Sequence[ProductMedia | CatalogMediaLinkView],
        variant_media: Mapping[int, Sequence[ProductVariantMedia | CatalogMediaLinkView]],
    ) -> ProductDetailResponse:
        return ProductDetailResponse(
            version=product.version,
            **self._product_scalars(product),
            **self._product_media(media_links),
            variants=[
                self.variant(variant, media_links=variant_media[variant.id]) for variant in variants
            ],
            media_assets=[
                ProductMediaAsset(
                    id=link.media.id,
                    role=link.role,
                    sort_order=link.sort_order,
                    url=self._media_url(link.media),
                    content_type=link.media.content_type,
                )
                for link in sorted(
                    media_links, key=lambda item: (item.role, item.sort_order, item.id)
                )
                if link.media.is_public
                and link.media.status == MediaStatus.READY.value
                and link.media.content_type in {"image/jpeg", "image/png", "image/webp"}
            ],
        )

    def variant(
        self,
        variant: ProductVariant,
        *,
        media_links: Sequence[ProductVariantMedia | CatalogMediaLinkView] | None = None,
    ) -> ProductVariantResponse:
        media = self._group_media(variant.media_links if media_links is None else media_links)
        return ProductVariantResponse(
            id=variant.id,
            product_id=variant.product_id,
            size=variant.size,
            color=variant.color,
            color_hex=variant.color_hex,
            stock_quantity=available_stock(variant),
            width_cm=self._optional_float(variant.width_cm),
            height_cm=self._optional_float(variant.height_cm),
            preview_image=self._first_url(
                media.get(ProductVariantMediaRole.PREVIEW_IMAGE.value, [])
            ),
            images=self._joined_urls(media.get(ProductVariantMediaRole.IMAGES.value, [])),
        )

    @staticmethod
    def _product_scalars(product: Product) -> dict[str, object]:
        return {
            "id": product.id,
            "title": product.title,
            "price": float(product.price),
            "old_price": CatalogResponseMapper._optional_float(product.old_price),
            "description": product.description,
            "composition": product.composition,
            "model_info": product.model_info,
            "sizes": ",".join(product.sizes),
            "colors": ",".join(product.colors),
            "is_active": product.is_active,
            "type": product.product_type,
            "weight": float(product.weight_kg),
            "height": float(product.height_cm),
            "width": float(product.width_cm),
            "length": float(product.length_cm),
            "stock_quantity": available_stock(product),
            "preset_source": product.preset_source or "garment_buro",
            "tags": product.tags or [],
            "slug": product.slug,
            "garment_model_id": product.garment_model_id,
            "category_id": product.category_id,
        }

    def _product_media(
        self, links: Sequence[ProductMedia | CatalogMediaLinkView]
    ) -> dict[str, str | None]:
        grouped = self._group_media(links)
        payload: dict[str, str | None] = {}
        for role in ProductMediaRole:
            role_links = grouped.get(role.value, [])
            payload[role.value] = (
                self._joined_urls(role_links)
                if role.value in PRODUCT_MULTI_MEDIA_ROLES
                else self._first_url(role_links)
            )
        return payload

    @staticmethod
    def _group_media(
        links: Sequence[ProductMedia | ProductVariantMedia | CatalogMediaLinkView],
    ) -> dict[str, list[MediaObject | CatalogMediaView]]:
        grouped: dict[str, list[MediaObject | CatalogMediaView]] = defaultdict(list)
        for link in sorted(links, key=lambda item: (item.role, item.sort_order, item.id)):
            if link.media.is_public and link.media.status == MediaStatus.READY.value:
                grouped[link.role].append(link.media)
        return grouped

    def _first_url(self, media: Sequence[MediaObject | CatalogMediaView]) -> str | None:
        return self._media_url(media[0]) if media else None

    def _joined_urls(self, media: Sequence[MediaObject | CatalogMediaView]) -> str | None:
        return ",".join(self._media_url(item) for item in media) if media else None

    def _media_url(self, media: MediaObject | CatalogMediaView) -> str:
        return public_media_url(self.settings, media)

    @staticmethod
    def _optional_float(value: object | None) -> float | None:
        return float(value) if value is not None else None
