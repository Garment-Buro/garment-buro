from __future__ import annotations

import hashlib
import json
from urllib.parse import unquote, urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    ProductDetailResponse,
    ProductResponse,
    ProductVariantResponse,
    ProductVariantWriteRequest,
    ProductWriteRequest,
)
from app.modules.media.models import (
    MediaObject,
    ProductMedia,
    ProductMediaRole,
    ProductVariantMedia,
    ProductVariantMediaRole,
)
from app.modules.media.repository import MediaRepository

PRODUCT_MULTI_MEDIA_ROLES = {
    ProductMediaRole.GALLERY_IMAGES.value,
    ProductMediaRole.DESKTOP_CARD_IMAGES.value,
    ProductMediaRole.DESKTOP_SLIDER_IMAGES.value,
    ProductMediaRole.MOBILE_SLIDER_IMAGES.value,
    ProductMediaRole.MOBILE_PRODUCT_SLIDER_IMAGES.value,
}


class CatalogProductNotFoundError(LookupError):
    pass


class CatalogVariantNotFoundError(LookupError):
    pass


class UnknownCatalogMediaError(ValueError):
    def __init__(self, missing_count: int) -> None:
        super().__init__(f"{missing_count} catalog media references are unknown or not ready")
        self.missing_count = missing_count


class CatalogInventoryReservedError(ValueError):
    pass


class CatalogService:
    def __init__(
        self,
        mapper: CatalogResponseMapper,
        repository: CatalogRepository | None = None,
    ) -> None:
        self.mapper = mapper
        self.repository = repository or CatalogRepository()

    async def list_products(self, session: AsyncSession) -> list[ProductResponse]:
        products = await self.repository.list_products(session)
        return [self.mapper.product(product) for product in products]

    async def get_product(
        self,
        session: AsyncSession,
        product_id: int,
    ) -> ProductDetailResponse | None:
        product = await self.repository.get_product(session, product_id)
        return self.mapper.product_detail(product) if product is not None else None

    async def list_variants(
        self,
        session: AsyncSession,
        product_id: int,
    ) -> list[ProductVariantResponse]:
        variants = await self.repository.list_variants(session, product_id)
        return [self.mapper.variant(variant) for variant in variants]


class CatalogWriteService:
    def __init__(
        self,
        settings: Settings,
        mapper: CatalogResponseMapper | None = None,
        repository: CatalogRepository | None = None,
        media_repository: MediaRepository | None = None,
    ) -> None:
        self.settings = settings
        self.mapper = mapper or CatalogResponseMapper(settings)
        self.repository = repository or CatalogRepository()
        self.media_repository = media_repository or MediaRepository()

    async def create_product(
        self,
        session: AsyncSession,
        *,
        payload: ProductWriteRequest,
        actor_user_id: int,
    ) -> ProductDetailResponse:
        media_by_url = await self._resolve_media(session, payload)
        product = Product()
        self._apply_scalars(product, payload)
        self._attach_children(product, payload, media_by_url)
        await self.repository.add_product(session, product)
        await self._audit(
            session,
            action="product.created",
            product=product,
            payload=payload,
            actor_user_id=actor_user_id,
        )
        return self.mapper.product_detail(product)

    async def update_product(
        self,
        session: AsyncSession,
        *,
        product_id: int,
        payload: ProductWriteRequest,
        actor_user_id: int,
    ) -> ProductDetailResponse:
        product = await self.repository.get_product_for_update(session, product_id)
        if product is None:
            raise CatalogProductNotFoundError(product_id)
        self._ensure_product_unreserved(product)
        media_by_url = await self._resolve_media(session, payload)
        await self.repository.clear_product_children(session, product)
        self._apply_scalars(product, payload)
        self._attach_children(product, payload, media_by_url)
        await session.flush()
        await self._audit(
            session,
            action="product.updated",
            product=product,
            payload=payload,
            actor_user_id=actor_user_id,
        )
        return self.mapper.product_detail(product)

    async def delete_product(
        self,
        session: AsyncSession,
        *,
        product_id: int,
        actor_user_id: int,
    ) -> None:
        product = await self.repository.get_product_for_update(session, product_id)
        if product is None:
            raise CatalogProductNotFoundError(product_id)
        self._ensure_product_unreserved(product)
        snapshot = self.mapper.product_detail(product).model_dump(mode="json")
        checksum = self._checksum(snapshot)
        await self.repository.delete_product(session, product)
        await self.repository.add_audit_event(
            session,
            action="product.deleted",
            product_id=product_id,
            actor_user_id=actor_user_id,
            snapshot_checksum_sha256=checksum,
            details={
                "variants_count": len(snapshot["variants"]),
                "media_references_count": self._response_media_count(snapshot),
            },
        )

    async def update_variant(
        self,
        session: AsyncSession,
        *,
        variant_id: int,
        payload: ProductVariantWriteRequest,
        actor_user_id: int,
    ) -> ProductVariantResponse:
        variant = await self.repository.get_variant_for_update(session, variant_id)
        if variant is None:
            raise CatalogVariantNotFoundError(variant_id)
        if variant.reserved_quantity:
            raise CatalogInventoryReservedError("Catalog variant has active reservations")
        references = self._variant_media_references(payload)
        media_by_url = await self._resolve_references(session, references)
        await self.repository.clear_variant_media(session, variant)
        variant.size = payload.size
        variant.color = payload.color
        variant.color_hex = payload.color_hex
        variant.stock_quantity = payload.stock_quantity
        variant.width_cm = payload.width_cm
        variant.height_cm = payload.height_cm
        self._attach_variant_media(variant, payload, media_by_url)
        await session.flush()
        snapshot = payload.model_dump(mode="json")
        snapshot.pop("id", None)
        await self.repository.add_audit_event(
            session,
            action="product.updated",
            product_id=variant.product_id,
            actor_user_id=actor_user_id,
            snapshot_checksum_sha256=self._checksum(snapshot),
            details={
                "scope": "variant",
                "variant_id": variant.id,
                "media_references_count": len(references),
            },
        )
        return self.mapper.variant(variant)

    @staticmethod
    def _ensure_product_unreserved(product: Product) -> None:
        if product.reserved_quantity or any(
            variant.reserved_quantity for variant in product.variants
        ):
            raise CatalogInventoryReservedError("Catalog product has active reservations")

    async def _resolve_media(
        self,
        session: AsyncSession,
        payload: ProductWriteRequest,
    ) -> dict[str, MediaObject]:
        return await self._resolve_references(session, self._media_references(payload))

    async def _resolve_references(
        self,
        session: AsyncSession,
        references: set[str],
    ) -> dict[str, MediaObject]:
        keys_by_url = {reference: self._object_key(reference) for reference in references}
        media_by_key = await self.media_repository.get_ready_by_keys(
            session,
            bucket_name=self.settings.minio_media_bucket,
            object_keys=set(keys_by_url.values()),
        )
        missing = [key for key in keys_by_url.values() if key not in media_by_key]
        if missing:
            raise UnknownCatalogMediaError(len(missing))
        return {url: media_by_key[key] for url, key in keys_by_url.items()}

    def _object_key(self, reference: str) -> str:
        if reference.startswith("/uploads/"):
            object_key = reference.removeprefix("/")
        else:
            parsed = urlsplit(reference)
            public = urlsplit(self.settings.minio_public_base_url or "")
            expected_prefix = f"/{self.settings.minio_media_bucket}/"
            if (
                parsed.scheme not in {"http", "https"}
                or (parsed.scheme, parsed.netloc) != (public.scheme, public.netloc)
                or not parsed.path.startswith(expected_prefix)
                or parsed.query
                or parsed.fragment
            ):
                raise UnknownCatalogMediaError(1)
            object_key = unquote(parsed.path.removeprefix(expected_prefix))
        parts = object_key.split("/")
        if (
            not object_key
            or len(object_key) > 1024
            or "\\" in object_key
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise UnknownCatalogMediaError(1)
        return object_key

    @staticmethod
    def _apply_scalars(product: Product, payload: ProductWriteRequest) -> None:
        product.title = payload.title
        product.price = payload.price
        product.old_price = payload.old_price
        product.description = payload.description
        product.composition = payload.composition
        product.model_info = payload.model_info
        product.sizes = CatalogWriteService._split_values(payload.sizes)
        product.colors = CatalogWriteService._split_values(payload.colors)
        product.is_active = payload.is_active
        product.product_type = payload.product_type
        product.weight_kg = payload.weight
        product.height_cm = payload.height
        product.width_cm = payload.width
        product.length_cm = payload.length
        product.stock_quantity = payload.stock_quantity

    def _attach_children(
        self,
        product: Product,
        payload: ProductWriteRequest,
        media_by_url: dict[str, MediaObject],
    ) -> None:
        for role in ProductMediaRole:
            references = self._split_media(getattr(payload, role.value))
            if role.value not in PRODUCT_MULTI_MEDIA_ROLES:
                references = references[:1]
            for sort_order, reference in enumerate(references):
                product.media_links.append(
                    ProductMedia(
                        media=media_by_url[reference],
                        role=role.value,
                        sort_order=sort_order,
                    )
                )
        for variant_payload in payload.variants:
            variant = ProductVariant(
                size=variant_payload.size,
                color=variant_payload.color,
                color_hex=variant_payload.color_hex,
                stock_quantity=variant_payload.stock_quantity,
                width_cm=variant_payload.width_cm,
                height_cm=variant_payload.height_cm,
            )
            self._attach_variant_media(variant, variant_payload, media_by_url)
            product.variants.append(variant)

    @staticmethod
    def _attach_variant_media(
        variant: ProductVariant,
        payload: ProductVariantWriteRequest,
        media_by_url: dict[str, MediaObject],
    ) -> None:
        role_values = {
            ProductVariantMediaRole.PREVIEW_IMAGE: CatalogWriteService._split_media(
                payload.preview_image
            )[:1],
            ProductVariantMediaRole.IMAGES: CatalogWriteService._split_media(payload.images),
        }
        for role, references in role_values.items():
            for sort_order, reference in enumerate(references):
                variant.media_links.append(
                    ProductVariantMedia(
                        media=media_by_url[reference],
                        role=role.value,
                        sort_order=sort_order,
                    )
                )

    async def _audit(
        self,
        session: AsyncSession,
        *,
        action: str,
        product: Product,
        payload: ProductWriteRequest,
        actor_user_id: int,
    ) -> None:
        snapshot = payload.model_dump(mode="json", by_alias=True)
        for variant in snapshot["variants"]:
            variant.pop("id", None)
        await self.repository.add_audit_event(
            session,
            action=action,
            product_id=product.id,
            actor_user_id=actor_user_id,
            snapshot_checksum_sha256=self._checksum(snapshot),
            details={
                "variants_count": len(payload.variants),
                "media_references_count": len(self._media_references(payload)),
            },
        )

    @staticmethod
    def _checksum(payload: dict[str, object]) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _split_values(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _split_media(value: str | None) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _media_references(payload: ProductWriteRequest) -> set[str]:
        references: set[str] = set()
        for role in ProductMediaRole:
            references.update(CatalogWriteService._split_media(getattr(payload, role.value)))
        for variant in payload.variants:
            references.update(CatalogWriteService._split_media(variant.preview_image))
            references.update(CatalogWriteService._split_media(variant.images))
        return references

    @staticmethod
    def _variant_media_references(payload: ProductVariantWriteRequest) -> set[str]:
        references = set(CatalogWriteService._split_media(payload.preview_image))
        references.update(CatalogWriteService._split_media(payload.images))
        return references

    @staticmethod
    def _response_media_count(snapshot: dict[str, object]) -> int:
        count = 0
        for role in ProductMediaRole:
            count += len(CatalogWriteService._split_media(snapshot.get(role.value)))
        for variant in snapshot["variants"]:
            count += len(CatalogWriteService._split_media(variant.get("preview_image")))
            count += len(CatalogWriteService._split_media(variant.get("images")))
        return count
