from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.carts.models import Cart, CartItem
from app.modules.carts.repository import CartRepository
from app.modules.carts.schemas import (
    CartItemResponse,
    CartItemWrite,
    CartSnapshotResponse,
    CartUpdateRequest,
    LegacyCartUpdateRequest,
)
from app.modules.carts.security import digest_cart_id, normalize_cart_id
from app.modules.catalog.pricing import price_customization, validate_customization
from app.modules.design_assets.references import design_image_tokens
from app.modules.design_assets.repository import DesignAssetRepository
from app.modules.identity.security import ensure_utc


class CartRevisionConflictError(ValueError):
    pass


class CartCatalogItemError(ValueError):
    pass


class CartMaintenanceService:
    def __init__(self, repository: CartRepository | None = None) -> None:
        self.repository = repository or CartRepository()

    async def purge_expired(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        batch_size: int = 500,
    ) -> int:
        if not 1 <= batch_size <= 5_000:
            raise ValueError("Cart purge batch size must be between 1 and 5000")
        carts = await self.repository.list_expired_for_update(
            session,
            now=now or datetime.now(timezone.utc),
            limit=batch_size,
        )
        if carts:
            await self.repository.delete_many(session, carts)
        return len(carts)


class CartService:
    def __init__(
        self,
        settings: Settings,
        repository: CartRepository | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or CartRepository()
        self.design_assets = DesignAssetRepository()

    async def get_snapshot(
        self,
        session: AsyncSession,
        *,
        cart_id: str,
        now: datetime | None = None,
    ) -> CartSnapshotResponse:
        normalized_id = normalize_cart_id(cart_id)
        cart = await self.repository.get_active(
            session,
            token_digest_sha256=digest_cart_id(normalized_id),
            now=now or datetime.now(timezone.utc),
        )
        return self._snapshot(normalized_id, cart)

    async def upsert_snapshot(
        self,
        session: AsyncSession,
        *,
        cart_id: str,
        payload: CartUpdateRequest,
        now: datetime | None = None,
    ) -> CartSnapshotResponse:
        normalized_id = normalize_cart_id(cart_id)
        current_time = now or datetime.now(timezone.utc)
        expires_at = current_time + timedelta(seconds=self.settings.cart_cache_ttl_seconds)
        cart = await self.repository.acquire(
            session,
            token_digest_sha256=digest_cart_id(normalized_id),
            expires_at=expires_at,
        )
        expired = ensure_utc(cart.expires_at) <= current_time
        digest = hashlib.sha256(
            json.dumps(
                payload.model_dump(mode="json"),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if cart.last_operation_id == payload.operation_id:
            if expired or cart.last_write_sha256 != digest:
                raise CartRevisionConflictError("Operation ID reused with different content")
            return self._snapshot(normalized_id, cart)
        revision = None if expired else cart.revision
        if payload.expected_revision != revision:
            raise CartRevisionConflictError("Cart changed since it was read")
        assets = await self.design_assets.lock_available(
            session,
            tokens=design_image_tokens(payload.items),
            bucket_name=self.settings.minio_customer_projects_bucket,
            now=current_time,
        )
        await self._replace_items(session, cart, payload.items, reprice_constructor=True)
        cart.revision = uuid4().hex
        cart.last_operation_id = payload.operation_id
        cart.last_write_sha256 = digest
        cart.updated_at_ms = int(current_time.timestamp() * 1000)
        cart.expires_at = expires_at
        await session.flush()
        await self.design_assets.replace_cart_links(session, cart_id=cart.id, assets=assets)
        return self._snapshot(normalized_id, cart)

    async def import_legacy_snapshot(
        self,
        session: AsyncSession,
        *,
        cart_id: str,
        payload: LegacyCartUpdateRequest,
        remaining_ttl_seconds: int | None,
        now: datetime | None = None,
    ) -> CartSnapshotResponse:
        ttl_seconds = (
            self.settings.cart_cache_ttl_seconds
            if remaining_ttl_seconds is None
            else remaining_ttl_seconds
        )
        if not 1 <= ttl_seconds <= self.settings.cart_cache_ttl_seconds:
            raise ValueError("Legacy cart TTL is outside the configured retention")
        normalized_id = normalize_cart_id(cart_id)
        current_time = now or datetime.now(timezone.utc)
        expires_at = current_time + timedelta(seconds=ttl_seconds)
        cart = await self.repository.acquire(
            session,
            token_digest_sha256=digest_cart_id(normalized_id),
            expires_at=expires_at,
        )
        assets = await self.design_assets.lock_available(
            session,
            tokens=design_image_tokens(payload.items),
            bucket_name=self.settings.minio_customer_projects_bucket,
            now=current_time,
        )
        await self._replace_items(session, cart, payload.items, reprice_constructor=False)
        cart.updated_at_ms = payload.updated_at_ms or int(current_time.timestamp() * 1000)
        cart.revision = uuid4().hex
        cart.last_operation_id = None
        cart.last_write_sha256 = None
        cart.expires_at = expires_at
        await session.flush()
        await self.design_assets.replace_cart_links(session, cart_id=cart.id, assets=assets)
        return self._snapshot(normalized_id, cart)

    async def _replace_items(
        self,
        session: AsyncSession,
        cart: Cart,
        items: list[CartItemWrite],
        *,
        reprice_constructor: bool,
    ) -> None:
        constructor_ids = {
            item.product_id
            for item in items
            if reprice_constructor and validate_customization(item.customization) is not None
        }
        base_prices = (
            await self.repository.product_prices(session, constructor_ids)
            if constructor_ids
            else {}
        )
        priced_items = []
        for item in items:
            if (
                item.product_id in constructor_ids
                and validate_customization(item.customization) is not None
            ):
                if item.product_id not in base_prices:
                    raise CartCatalogItemError("Cart contains an unavailable constructor product")
                price, customization = price_customization(
                    base_prices[item.product_id], item.customization
                )
                item = item.model_copy(update={"price": price, "customization": customization})
            priced_items.append(item)
        await self.repository.replace_items(
            session,
            cart,
            [self._item_model(item, position) for position, item in enumerate(priced_items)],
        )

    def _snapshot(self, cart_id: str, cart: Cart | None) -> CartSnapshotResponse:
        return CartSnapshotResponse(
            cart_id=cart_id,
            items=[self._item_response(item) for item in cart.items] if cart else [],
            revision=cart.revision if cart else None,
            updated_at_ms=cart.updated_at_ms if cart else 0,
            ttl_seconds=self.settings.cart_cache_ttl_seconds,
        )

    @staticmethod
    def _item_model(item: CartItemWrite, sort_order: int) -> CartItem:
        return CartItem(
            client_item_id=item.id,
            product_id_snapshot=item.product_id,
            title_snapshot=item.title,
            unit_price=item.price,
            image_url_snapshot=item.image,
            size_snapshot=item.size,
            color_snapshot=item.color,
            quantity=item.quantity,
            customization_snapshot=item.customization,
            sort_order=sort_order,
        )

    @staticmethod
    def _item_response(item: CartItem) -> CartItemResponse:
        return CartItemResponse(
            id=item.client_item_id,
            product_id=item.product_id_snapshot,
            title=item.title_snapshot,
            price=float(item.unit_price),
            image=item.image_url_snapshot,
            size=item.size_snapshot,
            color=item.color_snapshot,
            quantity=item.quantity,
            customization=item.customization_snapshot,
        )
