from __future__ import annotations

from collections import defaultdict
from urllib.parse import quote

from app.core.config import Settings
from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.schemas import (
    ProductDetailResponse,
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
        return ProductDetailResponse(
            **self._product_scalars(product),
            **self._product_media(product.media_links),
            variants=[self.variant(variant) for variant in product.variants],
        )

    def variant(self, variant: ProductVariant) -> ProductVariantResponse:
        media = self._group_media(variant.media_links)
        return ProductVariantResponse(
            id=variant.id,
            product_id=variant.product_id,
            size=variant.size,
            color=variant.color,
            color_hex=variant.color_hex,
            stock_quantity=variant.stock_quantity - variant.reserved_quantity,
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
            "stock_quantity": product.stock_quantity - product.reserved_quantity,
        }

    def _product_media(self, links: list[ProductMedia]) -> dict[str, str | None]:
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
        links: list[ProductMedia] | list[ProductVariantMedia],
    ) -> dict[str, list[MediaObject]]:
        grouped: dict[str, list[MediaObject]] = defaultdict(list)
        for link in sorted(links, key=lambda item: (item.role, item.sort_order, item.id)):
            if link.media.status == MediaStatus.READY.value:
                grouped[link.role].append(link.media)
        return grouped

    def _first_url(self, media: list[MediaObject]) -> str | None:
        return self._media_url(media[0]) if media else None

    def _joined_urls(self, media: list[MediaObject]) -> str | None:
        return ",".join(self._media_url(item) for item in media) if media else None

    def _media_url(self, media: MediaObject) -> str:
        if media.object_key.startswith("uploads/"):
            return f"/{media.object_key}"
        public_base_url = (self.settings.minio_public_base_url or "").rstrip("/")
        if not public_base_url:
            raise RuntimeError("MINIO_PUBLIC_BASE_URL is required to map catalog media")
        return f"{public_base_url}/{media.bucket_name}/{quote(media.object_key, safe='/')}"

    @staticmethod
    def _optional_float(value: object | None) -> float | None:
        return float(value) if value is not None else None
