from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from urllib.parse import unquote, urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.catalog.availability import load_availability
from app.modules.catalog.deletion_audit import catalog_deletion_audit
from app.modules.catalog.editor_commands import CatalogEditorCommands
from app.modules.catalog.editor_repository import CatalogEditorRepository
from app.modules.catalog.mapper import PRODUCT_MULTI_MEDIA_ROLES, CatalogResponseMapper
from app.modules.catalog.models import Product, ProductCategory, ProductVariant
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    ProductCategoryResponse,
    ProductCategoryWrite,
    ProductDetailResponse,
    ProductResponse,
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


class CatalogProductNotFoundError(LookupError):
    pass


class UnknownCatalogMediaError(ValueError):
    def __init__(self, missing_count: int) -> None:
        super().__init__(f"{missing_count} catalog media references are unknown or not ready")
        self.missing_count = missing_count


class CatalogInventoryReservedError(ValueError):
    pass


class CatalogReferenceNotFoundError(LookupError):
    pass


class CatalogVersionConflictError(RuntimeError):
    pass


class CatalogProductVersionConflictError(CatalogVersionConflictError):
    pass


def product_version_conflict_detail() -> dict[str, str]:
    return {
        "code": "catalog_product_version_conflict",
        "message": "Товар изменился после открытия формы. Ваши правки не сохранены. "
        "Откройте актуальную версию перед повторным сохранением.",
    }


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
        await load_availability(session, products)
        return [self.mapper.product(product) for product in products]

    async def get_product(
        self,
        session: AsyncSession,
        product_id: int,
        *,
        public_only: bool = False,
    ) -> ProductDetailResponse | None:
        product = await self.repository.get_product(session, product_id, public_only=public_only)
        if product is not None:
            await load_availability(session, [product])
        return self.mapper.product_detail(product) if product is not None else None


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
        await self._validate_product_references(session, payload)
        media_by_url = await self._resolve_media(session, payload)
        product = Product(version=1, variants=[], media_links=[])
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
        await load_availability(session, [product])
        return self.mapper.product_detail(product)

    async def update_product(
        self,
        session: AsyncSession,
        *,
        product_id: int,
        expected_version: int,
        payload: ProductWriteRequest,
        actor_user_id: int,
    ) -> ProductDetailResponse:
        product = await self.repository.get_product_for_update(session, product_id)
        if product is None:
            raise CatalogProductNotFoundError(product_id)
        if product.version != expected_version:
            raise CatalogProductVersionConflictError("Product version has changed")
        variants = await CatalogEditorRepository.variants(session, product.id)
        existing = {variant.id: variant for variant in variants}
        requested_ids = [variant.id for variant in payload.variants if variant.id is not None]
        if len(requested_ids) != len(set(requested_ids)) or any(
            vid not in existing for vid in requested_ids
        ):
            raise CatalogReferenceNotFoundError("Variant identity does not belong to this product")
        await self._ensure_product_unreserved(session, product)
        if await self.repository.has_fabric_holds(session, product.id):
            raise CatalogInventoryReservedError("Preset has active fabric reservations")
        await self._validate_product_references(session, payload)
        media_by_url = await self._resolve_media(session, payload)
        await CatalogEditorCommands.clear_media(
            session, product_id=product.id, variant_ids=set(existing)
        )
        retained_ids = set(requested_ids)
        for variant_id, variant in existing.items():
            if variant_id not in retained_ids:
                await session.delete(variant)
        # Remove omitted selections before inserting their replacements (unique FK tuple).
        await session.flush()
        self._apply_scalars(product, payload)
        selected = []
        for variant_payload in payload.variants:
            variant = existing.get(variant_payload.id)
            created = variant is None
            if created:
                variant = ProductVariant(product_id=product.id)
                session.add(variant)
            self._apply_variant(variant, variant_payload, payload, created=created)
            selected.append((variant, variant_payload))
        product.version += 1
        await session.flush()
        await CatalogEditorCommands.add_media(
            session,
            ProductMedia,
            (
                {
                    "product_id": product.id,
                    "media_object_id": media.id,
                    "role": role,
                    "sort_order": order,
                }
                for role, order, media in self._product_media(payload, media_by_url)
            ),
        )
        await CatalogEditorCommands.add_media(
            session,
            ProductVariantMedia,
            (
                {
                    "product_variant_id": variant.id,
                    "media_object_id": media.id,
                    "role": role,
                    "sort_order": order,
                }
                for variant, variant_payload in selected
                for role, order, media in self._variant_media(variant_payload, media_by_url)
            ),
        )
        await self._audit(
            session,
            action="product.updated",
            product=product,
            payload=payload,
            actor_user_id=actor_user_id,
        )
        source = await CatalogEditorRepository.media_snapshot(
            session,
            product,
            sorted((variant for variant, _ in selected), key=lambda row: row.id),
            settings=self.settings,
        )
        await load_availability(
            session, [source.product], variants_by_product={product.id: source.variants}
        )
        return self.mapper.product_detail_from_parts(
            source.product, source.variants, source.media_links, source.variant_media
        )

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
        await self._ensure_product_unreserved(session, product)
        if await self.repository.has_fabric_holds(session, product.id):
            raise CatalogInventoryReservedError("Preset has active fabric reservations")
        evidence = await catalog_deletion_audit(session, product)
        await self.repository.delete_product(session, product)
        await self.repository.add_audit_event(
            session,
            action="product.deleted",
            product_id=product_id,
            actor_user_id=actor_user_id,
            snapshot_checksum_sha256=evidence.checksum,
            details=evidence.details(),
        )

    async def create_category(
        self,
        session: AsyncSession,
        *,
        payload: ProductCategoryWrite,
    ) -> ProductCategoryResponse:
        category = ProductCategory(version=1)
        self._apply_category(category, payload)
        await self.repository.add_category(session, category)
        return ProductCategoryResponse.model_validate(category)

    async def update_category(
        self,
        session: AsyncSession,
        *,
        category_id: int,
        expected_version: int,
        payload: ProductCategoryWrite,
    ) -> ProductCategoryResponse:
        category = await self.repository.get_category(session, category_id, lock=True)
        if category is None:
            raise CatalogReferenceNotFoundError("Product category was not found")
        if category.version != expected_version:
            raise CatalogVersionConflictError("Product category version has changed")
        self._apply_category(category, payload)
        category.version += 1
        await session.flush()
        return ProductCategoryResponse.model_validate(category)

    async def _validate_product_references(
        self,
        session: AsyncSession,
        payload: ProductWriteRequest,
    ) -> None:
        if payload.category_id is not None and not await self.repository.active_category_exists(
            session, payload.category_id
        ):
            raise CatalogReferenceNotFoundError("Active product category was not found")
        if payload.garment_model_id is not None and not await self.repository.garment_model_exists(
            session, payload.garment_model_id
        ):
            raise CatalogReferenceNotFoundError("Active garment model was not found")
        size_ids = {
            row.garment_size_id for row in payload.variants if row.garment_size_id is not None
        }
        fabric_ids = {row.fabric_id for row in payload.variants if row.fabric_id is not None}
        if not size_ids and not fabric_ids:
            return
        if payload.garment_model_id is None:
            raise CatalogReferenceNotFoundError(
                "Variant size and fabric references require a garment model"
            )
        sizes = await self.repository.active_size_codes(
            session, garment_model_id=payload.garment_model_id, size_ids=size_ids
        )
        fabrics = await self.repository.allowed_active_fabric_ids(
            session, garment_model_id=payload.garment_model_id, fabric_ids=fabric_ids
        )
        for variant in payload.variants:
            if variant.garment_size_id is not None and (
                variant.garment_size_id not in sizes
                or (variant.size is not None and variant.size != sizes[variant.garment_size_id])
            ):
                raise CatalogReferenceNotFoundError(
                    "Variant garment size must match its active garment model and size code"
                )
            if variant.fabric_id is not None and variant.fabric_id not in fabrics:
                raise CatalogReferenceNotFoundError(
                    "Variant fabric must be active and allowed for its garment model"
                )

    async def _ensure_product_unreserved(self, session: AsyncSession, product: Product) -> None:
        if product.reserved_quantity or await self.repository.has_reserved_variants(
            session, product.id
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
        if "preset_source" in payload.model_fields_set or product.id is None:
            product.preset_source = payload.preset_source
        if "tags" in payload.model_fields_set or product.id is None:
            product.tags = payload.tags
        product.title = payload.title
        product.slug = payload.slug
        product.category_id = payload.category_id
        product.garment_model_id = payload.garment_model_id
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
        if payload.garment_model_id is None:
            product.stock_quantity = payload.stock_quantity
        elif product.id is None:
            product.stock_quantity = 0

    @staticmethod
    def _apply_category(category: ProductCategory, payload: ProductCategoryWrite) -> None:
        category.slug = payload.slug
        category.name = payload.name
        category.description = payload.description
        category.is_active = payload.is_active

    def _attach_children(
        self,
        product: Product,
        payload: ProductWriteRequest,
        media_by_url: dict[str, MediaObject],
    ) -> None:
        for role, order, media in self._product_media(payload, media_by_url):
            product.media_links.append(ProductMedia(media=media, role=role, sort_order=order))
        for variant_payload in payload.variants:
            variant = ProductVariant(media_links=[])
            self._apply_variant(variant, variant_payload, payload, created=True)
            for role, order, media in self._variant_media(variant_payload, media_by_url):
                variant.media_links.append(
                    ProductVariantMedia(media=media, role=role, sort_order=order)
                )
            product.variants.append(variant)

    @staticmethod
    def _apply_variant(
        variant: ProductVariant,
        variant_payload: ProductVariantWriteRequest,
        payload: ProductWriteRequest,
        *,
        created: bool,
    ) -> None:
        variant.size = variant_payload.size
        variant.garment_size_id = variant_payload.garment_size_id
        variant.fabric_id = variant_payload.fabric_id
        variant.color = variant_payload.color
        variant.color_hex = variant_payload.color_hex
        if payload.garment_model_id is None:
            variant.stock_quantity = variant_payload.stock_quantity
        elif created:
            variant.stock_quantity = 0
        variant.width_cm = variant_payload.width_cm
        variant.height_cm = variant_payload.height_cm

    @staticmethod
    def _product_media(
        payload: ProductWriteRequest, media_by_url: dict[str, MediaObject]
    ) -> Iterator[tuple[str, int, MediaObject]]:
        for role in ProductMediaRole:
            references = CatalogWriteService._split_media(getattr(payload, role.value))
            if role.value not in PRODUCT_MULTI_MEDIA_ROLES:
                references = references[:1]
            for sort_order, reference in enumerate(references):
                yield role.value, sort_order, media_by_url[reference]

    @staticmethod
    def _variant_media(
        payload: ProductVariantWriteRequest,
        media_by_url: dict[str, MediaObject],
    ) -> Iterator[tuple[str, int, MediaObject]]:
        role_values = {
            ProductVariantMediaRole.PREVIEW_IMAGE: CatalogWriteService._split_media(
                payload.preview_image
            )[:1],
            ProductVariantMediaRole.IMAGES: CatalogWriteService._split_media(payload.images),
        }
        for role, references in role_values.items():
            for sort_order, reference in enumerate(references):
                yield role.value, sort_order, media_by_url[reference]

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
