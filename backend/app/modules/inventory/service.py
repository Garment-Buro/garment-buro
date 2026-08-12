from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.catalog.models import Product, ProductVariant
from app.modules.identity.security import ensure_utc
from app.modules.inventory.models import InventoryReservation, InventoryReservationStatus
from app.modules.inventory.repository import InventoryRepository
from app.modules.orders.models import Order


class InsufficientStockError(ValueError):
    pass


class InventoryReservationStateError(ValueError):
    pass


class InventoryReservationExpiredError(ValueError):
    pass


class InventoryReservationService:
    def __init__(
        self,
        settings: Settings,
        repository: InventoryRepository | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or InventoryRepository()

    async def reserve_order(
        self,
        session: AsyncSession,
        *,
        order: Order,
        products_by_id: dict[int, Product],
        now: datetime | None = None,
    ) -> None:
        if order.id is None or any(item.id is None for item in order.items):
            raise RuntimeError("Order and items must be flushed before reservation")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        expires_at = current_time + timedelta(
            seconds=self.settings.inventory_reservation_ttl_seconds
        )
        product_requirements: dict[int, int] = {}
        variant_requirements: dict[int, int] = {}
        variants_by_id: dict[int, ProductVariant] = {}
        for item in order.items:
            product = products_by_id.get(item.product_id_snapshot)
            if product is None:
                raise RuntimeError("Locked order product is missing")
            product_requirements[product.id] = (
                product_requirements.get(product.id, 0) + item.quantity
            )
            variant = self._variant(product, item.variant_id_snapshot)
            if variant is not None:
                variants_by_id[variant.id] = variant
                variant_requirements[variant.id] = (
                    variant_requirements.get(variant.id, 0) + item.quantity
                )
        self._validate_available(products_by_id, product_requirements, "product")
        self._validate_available(variants_by_id, variant_requirements, "variant")
        for product_id, quantity in product_requirements.items():
            products_by_id[product_id].reserved_quantity += quantity
        for variant_id, quantity in variant_requirements.items():
            variants_by_id[variant_id].reserved_quantity += quantity

        reservations: list[InventoryReservation] = []
        for item in order.items:
            reservations.append(
                InventoryReservation(
                    order_id=order.id,
                    order_item_id=item.id,
                    product_id_snapshot=item.product_id_snapshot,
                    variant_id_snapshot=item.variant_id_snapshot,
                    quantity=item.quantity,
                    status=InventoryReservationStatus.ACTIVE.value,
                    expires_at=expires_at,
                    resolved_at=None,
                    resolution_reason=None,
                    version=1,
                )
            )
        await self.repository.add_reservations(session, reservations)

    async def confirm_order(
        self,
        session: AsyncSession,
        *,
        order: Order,
        now: datetime | None = None,
    ) -> bool:
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        reservations = await self.repository.list_order_reservations_for_update(
            session,
            order_id=order.id,
        )
        if reservations and all(
            reservation.status == InventoryReservationStatus.CONFIRMED.value
            for reservation in reservations
        ):
            return False
        self._require_all_active(reservations)
        if any(ensure_utc(reservation.expires_at) <= current_time for reservation in reservations):
            raise InventoryReservationExpiredError("Order inventory reservation has expired")
        products, variants = await self._lock_reservation_stock(session, reservations)
        product_requirements, variant_requirements = self._requirements(reservations)
        self._validate_confirmable(products, product_requirements, "product")
        self._validate_confirmable(variants, variant_requirements, "variant")
        for product_id, quantity in product_requirements.items():
            products[product_id].reserved_quantity -= quantity
            products[product_id].stock_quantity -= quantity
        for variant_id, quantity in variant_requirements.items():
            variants[variant_id].reserved_quantity -= quantity
            variants[variant_id].stock_quantity -= quantity
        for reservation in reservations:
            self._resolve(
                reservation,
                status=InventoryReservationStatus.CONFIRMED,
                reason="payment.confirmed",
                now=current_time,
            )
        await session.flush()
        return True

    async def refresh_active_order(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        now: datetime | None = None,
    ) -> datetime:
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        reservations = await self.repository.list_order_reservations_for_update(
            session,
            order_id=order_id,
        )
        self._require_all_active(reservations)
        if any(ensure_utc(reservation.expires_at) <= current_time for reservation in reservations):
            raise InventoryReservationExpiredError("Order inventory reservation has expired")
        refreshed_until = current_time + timedelta(
            seconds=self.settings.inventory_reservation_ttl_seconds
        )
        for reservation in reservations:
            if ensure_utc(reservation.expires_at) < refreshed_until:
                reservation.expires_at = refreshed_until
                reservation.version += 1
        await session.flush()
        return refreshed_until

    async def release_order(
        self,
        session: AsyncSession,
        *,
        order: Order,
        reason: str,
        expired: bool = False,
        now: datetime | None = None,
    ) -> bool:
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        reservations = await self.repository.list_order_reservations_for_update(
            session,
            order_id=order.id,
        )
        terminal_statuses = {
            InventoryReservationStatus.RELEASED.value,
            InventoryReservationStatus.EXPIRED.value,
        }
        if reservations and all(
            reservation.status in terminal_statuses for reservation in reservations
        ):
            return False
        self._require_all_active(reservations)
        products, variants = await self._lock_reservation_stock(session, reservations)
        target = (
            InventoryReservationStatus.EXPIRED if expired else InventoryReservationStatus.RELEASED
        )
        product_requirements, variant_requirements = self._requirements(reservations)
        self._validate_releasable(products, product_requirements, "product")
        self._validate_releasable(variants, variant_requirements, "variant")
        for product_id, quantity in product_requirements.items():
            products[product_id].reserved_quantity -= quantity
        for variant_id, quantity in variant_requirements.items():
            variants[variant_id].reserved_quantity -= quantity
        for reservation in reservations:
            self._resolve(
                reservation,
                status=target,
                reason=reason,
                now=current_time,
            )
        await session.flush()
        return True

    async def _lock_reservation_stock(
        self,
        session: AsyncSession,
        reservations: list[InventoryReservation],
    ) -> tuple[dict[int, Product], dict[int, ProductVariant]]:
        return await self.repository.lock_stock(
            session,
            product_ids={reservation.product_id_snapshot for reservation in reservations},
            variant_ids={
                reservation.variant_id_snapshot
                for reservation in reservations
                if reservation.variant_id_snapshot is not None
            },
        )

    @staticmethod
    def _require_all_active(reservations: list[InventoryReservation]) -> None:
        if not reservations:
            raise InventoryReservationStateError("Order has no inventory reservations")
        if any(
            reservation.status != InventoryReservationStatus.ACTIVE.value
            for reservation in reservations
        ):
            raise InventoryReservationStateError("Order inventory reservations are mixed")

    @staticmethod
    def _variant(product: Product, variant_id: int | None) -> ProductVariant | None:
        if variant_id is None:
            return None
        variant = next((item for item in product.variants if item.id == variant_id), None)
        if variant is None:
            raise RuntimeError("Locked order variant is missing")
        return variant

    @staticmethod
    def _validate_available(
        stocks: dict[int, Product] | dict[int, ProductVariant],
        requirements: dict[int, int],
        scope: str,
    ) -> None:
        for stock_id, quantity in requirements.items():
            stock = stocks.get(stock_id)
            if stock is None:
                raise RuntimeError(f"Reserved {scope} is missing")
            if stock.stock_quantity - stock.reserved_quantity < quantity:
                raise InsufficientStockError(f"Insufficient {scope} stock")

    @staticmethod
    def _validate_confirmable(
        stocks: dict[int, Product] | dict[int, ProductVariant],
        requirements: dict[int, int],
        scope: str,
    ) -> None:
        for stock_id, quantity in requirements.items():
            stock = stocks.get(stock_id)
            if stock is None:
                raise RuntimeError(f"Reserved {scope} is missing")
            if stock.reserved_quantity < quantity or stock.stock_quantity < quantity:
                raise InventoryReservationStateError(f"Invalid {scope} reservation counters")

    @staticmethod
    def _validate_releasable(
        stocks: dict[int, Product] | dict[int, ProductVariant],
        requirements: dict[int, int],
        scope: str,
    ) -> None:
        for stock_id, quantity in requirements.items():
            stock = stocks.get(stock_id)
            if stock is None:
                raise RuntimeError(f"Reserved {scope} is missing")
            if stock.reserved_quantity < quantity:
                raise InventoryReservationStateError(f"Invalid {scope} reservation counter")

    @staticmethod
    def _requirements(
        reservations: list[InventoryReservation],
    ) -> tuple[dict[int, int], dict[int, int]]:
        products: dict[int, int] = {}
        variants: dict[int, int] = {}
        for reservation in reservations:
            products[reservation.product_id_snapshot] = (
                products.get(reservation.product_id_snapshot, 0) + reservation.quantity
            )
            if reservation.variant_id_snapshot is not None:
                variants[reservation.variant_id_snapshot] = (
                    variants.get(reservation.variant_id_snapshot, 0) + reservation.quantity
                )
        return products, variants

    @staticmethod
    def _resolve(
        reservation: InventoryReservation,
        *,
        status: InventoryReservationStatus,
        reason: str,
        now: datetime,
    ) -> None:
        reservation.status = status.value
        reservation.resolved_at = now
        reservation.resolution_reason = reason[:64]
        reservation.version += 1
