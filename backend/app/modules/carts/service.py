from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.carts.models import Cart, CartItem
from app.modules.carts.repository import CartRepository
from app.modules.carts.schemas import (
    CartDeletedResponse,
    CartItemResponse,
    CartItemWrite,
    CartSnapshotResponse,
    CartUpdatedResponse,
    CartUpdateRequest,
)
from app.modules.carts.security import digest_cart_id, normalize_cart_id
from app.modules.identity.security import ensure_utc

MAX_CLIENT_CLOCK_SKEW = timedelta(minutes=5)


class CartTimestampError(ValueError):
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
    ) -> CartUpdatedResponse:
        return await self._upsert_snapshot(
            session,
            cart_id=cart_id,
            payload=payload,
            now=now,
            ttl_seconds=self.settings.cart_cache_ttl_seconds,
            validate_client_clock=True,
        )

    async def import_legacy_snapshot(
        self,
        session: AsyncSession,
        *,
        cart_id: str,
        payload: CartUpdateRequest,
        remaining_ttl_seconds: int | None,
        now: datetime | None = None,
    ) -> CartUpdatedResponse:
        ttl_seconds = (
            self.settings.cart_cache_ttl_seconds
            if remaining_ttl_seconds is None
            else remaining_ttl_seconds
        )
        if not 1 <= ttl_seconds <= self.settings.cart_cache_ttl_seconds:
            raise ValueError("Legacy cart TTL is outside the configured retention")
        return await self._upsert_snapshot(
            session,
            cart_id=cart_id,
            payload=payload,
            now=now,
            ttl_seconds=ttl_seconds,
            validate_client_clock=False,
        )

    async def _upsert_snapshot(
        self,
        session: AsyncSession,
        *,
        cart_id: str,
        payload: CartUpdateRequest,
        now: datetime | None,
        ttl_seconds: int,
        validate_client_clock: bool,
    ) -> CartUpdatedResponse:
        normalized_id = normalize_cart_id(cart_id)
        current_time = now or datetime.now(timezone.utc)
        current_time_ms = int(current_time.timestamp() * 1000)
        client_updated_at_ms = payload.updated_at_ms or current_time_ms
        if validate_client_clock and client_updated_at_ms > int(
            (current_time + MAX_CLIENT_CLOCK_SKEW).timestamp() * 1000
        ):
            raise CartTimestampError("Cart timestamp is too far in the future")
        expires_at = current_time + timedelta(seconds=ttl_seconds)
        cart = await self.repository.acquire(
            session,
            token_digest_sha256=digest_cart_id(normalized_id),
            expires_at=expires_at,
        )
        expired = ensure_utc(cart.expires_at) <= current_time
        stored_timestamp_is_untrusted_future = cart.client_updated_at_ms > int(
            (current_time + MAX_CLIENT_CLOCK_SKEW).timestamp() * 1000
        )
        if (
            not expired
            and not stored_timestamp_is_untrusted_future
            and client_updated_at_ms < cart.client_updated_at_ms
        ):
            return self._updated(normalized_id, cart)

        is_new = cart.client_updated_at_ms == 0 and not cart.items
        items = [
            self._item_model(item, sort_order) for sort_order, item in enumerate(payload.items)
        ]
        await self.repository.replace_items(session, cart, items)
        cart.client_updated_at_ms = client_updated_at_ms
        cart.version = 1 if expired or is_new else cart.version + 1
        cart.expires_at = expires_at
        await session.flush()
        return self._updated(normalized_id, cart)

    async def delete_snapshot(
        self,
        session: AsyncSession,
        *,
        cart_id: str,
    ) -> CartDeletedResponse:
        normalized_id = normalize_cart_id(cart_id)
        cart = await self.repository.get_for_update(
            session,
            token_digest_sha256=digest_cart_id(normalized_id),
        )
        if cart is not None:
            await self.repository.delete(session, cart)
        return CartDeletedResponse(cart_id=normalized_id)

    def _snapshot(self, cart_id: str, cart: Cart | None) -> CartSnapshotResponse:
        return CartSnapshotResponse(
            cart_id=cart_id,
            items=[self._item_response(item) for item in cart.items] if cart else [],
            updated_at_ms=cart.client_updated_at_ms if cart else 0,
            ttl_seconds=self.settings.cart_cache_ttl_seconds,
        )

    def _updated(self, cart_id: str, cart: Cart) -> CartUpdatedResponse:
        return CartUpdatedResponse(
            cart_id=cart_id,
            items_count=len(cart.items),
            updated_at_ms=cart.client_updated_at_ms,
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
