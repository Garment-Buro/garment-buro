from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.repository import CatalogRepository
from app.modules.delivery.constants import CDEK_DELIVERY_METHODS
from app.modules.fulfillment.service import FulfillmentOutboxService
from app.modules.identity.models import User, UserStatus
from app.modules.identity.security import OtpSecurity, ensure_utc, normalize_email
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.service import InventoryReservationService
from app.modules.orders.legacy import LegacyOrderReader
from app.modules.orders.models import (
    Order,
    OrderGuestAccess,
    OrderItem,
    OrderPaymentStatus,
    OrderStatus,
    OrderStatusHistory,
)
from app.modules.orders.repository import (
    LegacyOrderClaimRepository,
    OrderRepository,
    TargetOrderReadRepository,
)
from app.modules.orders.schemas import (
    LegacyOrderResponse,
    OrderCreationCommand,
    OrderCreationResult,
    OrderLineCreate,
)
from app.modules.orders.security import (
    digest_order_guest_access_token,
    digest_order_idempotency_key,
)

MONEY_QUANTUM = Decimal("0.01")


class OrderIdempotencyConflictError(ValueError):
    pass


class OrderCatalogItemError(ValueError):
    pass


class OrderTotalMismatchError(ValueError):
    pass


class OrderNotFoundError(LookupError):
    pass


class InvalidOrderTransitionError(ValueError):
    pass


class OrderGuestAccessStateError(ValueError):
    pass


class OwnedOrderService(Protocol):
    async def list_owned_orders(
        self,
        session: AsyncSession,
        *,
        user: User,
    ) -> list[LegacyOrderResponse]: ...


class OrderGuestAccessService:
    def __init__(
        self,
        settings: Settings,
        repository: TargetOrderReadRepository | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or TargetOrderReadRepository()

    async def register(
        self,
        session: AsyncSession,
        *,
        order: Order,
        token: str,
        now: datetime | None = None,
    ) -> None:
        if order.id is None:
            raise RuntimeError("Order must be flushed before guest access registration")
        if order.user_id is not None:
            raise OrderGuestAccessStateError("Authenticated order must not receive guest access")
        if await self.repository.is_legacy_import(session, order_id=order.id):
            raise OrderGuestAccessStateError(
                "Imported order must not receive retrospective guest access"
            )
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        access = OrderGuestAccess(
            order_id=order.id,
            token_digest_sha256=digest_order_guest_access_token(token),
            expires_at=current_time + timedelta(days=self.settings.order_guest_access_ttl_days),
            revoked_at=None,
            created_at=current_time,
            updated_at=current_time,
        )
        await self.repository.add_guest_access(session, access)

    async def resolve(
        self,
        session: AsyncSession,
        *,
        token: str,
        now: datetime | None = None,
    ) -> LegacyOrderResponse | None:
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        order = await self.repository.get_by_guest_digest(
            session,
            token_digest_sha256=digest_order_guest_access_token(token),
            now=current_time,
        )
        return TargetOrderReadService.map_order(order) if order is not None else None

    async def revoke(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        now: datetime | None = None,
    ) -> bool:
        access = await self.repository.get_guest_access_for_update(
            session,
            order_id=order_id,
        )
        if access is None:
            raise OrderGuestAccessStateError("Order has no guest access")
        if access.revoked_at is not None:
            return False
        access.revoked_at = ensure_utc(now or datetime.now(timezone.utc))
        await session.flush()
        return True


class OrderCreationService:
    def __init__(
        self,
        settings: Settings | None = None,
        repository: OrderRepository | None = None,
        catalog_repository: CatalogRepository | None = None,
        inventory_service: InventoryReservationService | None = None,
        guest_access_service: OrderGuestAccessService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or OrderRepository()
        self.catalog_repository = catalog_repository or CatalogRepository()
        self.inventory_service = inventory_service or InventoryReservationService(self.settings)
        self.guest_access_service = guest_access_service or OrderGuestAccessService(self.settings)

    async def create(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        command: OrderCreationCommand,
        user_id: int | None = None,
        guest_access_token: str | None = None,
        now: datetime | None = None,
    ) -> OrderCreationResult:
        key_digest = digest_order_idempotency_key(idempotency_key)
        guest_access_digest = (
            digest_order_guest_access_token(guest_access_token)
            if guest_access_token is not None
            else None
        )
        if user_id is not None and guest_access_digest is not None:
            raise OrderGuestAccessStateError("Authenticated order must not receive guest access")
        fingerprint = self._request_fingerprint(
            command,
            user_id=user_id,
            guest_access_digest=guest_access_digest,
        )
        creation_request = await self.repository.acquire_creation_request(
            session,
            key_digest_sha256=key_digest,
            request_fingerprint_sha256=fingerprint,
        )
        if creation_request.request_fingerprint_sha256 != fingerprint:
            raise OrderIdempotencyConflictError(
                "Order idempotency key was already used for another request"
            )
        if creation_request.order_id is not None:
            existing = await self.repository.get_order(session, creation_request.order_id)
            if existing is None:
                raise RuntimeError("Completed order creation request has no order")
            return self._result(existing, replayed=True)

        products = await self.catalog_repository.get_order_products_for_update(
            session,
            {item.product_id for item in command.items},
        )
        products_by_id = {product.id: product for product in products}
        requires_delivery_measurements = command.delivery_method in CDEK_DELIVERY_METHODS
        if (
            requires_delivery_measurements
            and sum(item.quantity for item in command.items) > self.settings.cdek_max_packages
        ):
            raise OrderCatalogItemError("CDEK order contains too many packages")
        order_items = [
            self._order_item(
                item,
                products_by_id,
                sort_order,
                requires_delivery_measurements=requires_delivery_measurements,
            )
            for sort_order, item in enumerate(command.items)
        ]
        items_subtotal = sum(
            (item.line_total for item in order_items),
            start=Decimal("0.00"),
        ).quantize(MONEY_QUANTUM)
        delivery_price = command.delivery_price.quantize(MONEY_QUANTUM)
        total_price = (items_subtotal + delivery_price).quantize(MONEY_QUANTUM)
        if total_price != command.claimed_total_price.quantize(MONEY_QUANTUM):
            raise OrderTotalMismatchError("Claimed order total does not match server prices")

        email, email_normalized = normalize_email(command.email)
        order = Order(
            user_id=user_id,
            email=email,
            email_normalized=email_normalized,
            phone=command.phone,
            first_name=command.first_name,
            last_name=command.last_name,
            patronymic=command.patronymic,
            delivery_city=command.delivery_city,
            delivery_method=command.delivery_method,
            delivery_address=command.delivery_address,
            cdek_point_code=command.cdek_point_code,
            payment_method=command.payment_method,
            items_subtotal=items_subtotal,
            delivery_price=delivery_price,
            total_price=total_price,
            currency=command.currency,
            status=OrderStatus.NEW.value,
            payment_status=OrderPaymentStatus.PENDING.value,
            version=1,
            request_fingerprint_sha256=fingerprint,
        )
        order.items.extend(order_items)
        order.status_history.append(
            OrderStatusHistory(
                version=1,
                from_status=None,
                to_status=OrderStatus.NEW.value,
                reason_code="order.created",
                actor_user_id=user_id,
                details={"items_count": len(order_items)},
            )
        )
        await self.repository.add_order(session, order)
        await self.inventory_service.reserve_order(
            session,
            order=order,
            products_by_id=products_by_id,
            now=now,
        )
        if guest_access_token is not None:
            await self.guest_access_service.register(
                session,
                order=order,
                token=guest_access_token,
                now=now,
            )
        creation_request.order_id = order.id
        await session.flush()
        return self._result(order, replayed=False)

    @staticmethod
    def _order_item(
        item: OrderLineCreate,
        products_by_id: dict[int, Product],
        sort_order: int,
        *,
        requires_delivery_measurements: bool,
    ) -> OrderItem:
        product = products_by_id.get(item.product_id)
        if product is None or not product.is_active:
            raise OrderCatalogItemError("Order contains an unavailable product")
        variant = OrderCreationService._resolve_variant(product, item)
        unit_price = product.price.quantize(MONEY_QUANTUM)
        delivery_measurements = OrderCreationService._delivery_measurements(
            product,
            required=requires_delivery_measurements,
        )
        return OrderItem(
            client_item_id=item.id,
            product_id_snapshot=product.id,
            variant_id_snapshot=variant.id if variant is not None else None,
            sku_snapshot=variant.sku if variant is not None else None,
            title_snapshot=product.title,
            unit_price=unit_price,
            quantity=item.quantity,
            line_total=(unit_price * item.quantity).quantize(MONEY_QUANTUM),
            image_url_snapshot=item.image,
            size_snapshot=item.size,
            color_snapshot=item.color,
            customization_snapshot=item.customization,
            delivery_weight_kg_snapshot=delivery_measurements[0],
            delivery_height_cm_snapshot=delivery_measurements[1],
            delivery_width_cm_snapshot=delivery_measurements[2],
            delivery_length_cm_snapshot=delivery_measurements[3],
            sort_order=sort_order,
        )

    @staticmethod
    def _delivery_measurements(
        product: Product,
        *,
        required: bool,
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
        values = (
            product.weight_kg,
            product.height_cm,
            product.width_cm,
            product.length_cm,
        )
        if all(value > 0 for value in values):
            return values
        if required:
            raise OrderCatalogItemError("CDEK order product has incomplete logistics measurements")
        return (None, None, None, None)

    @staticmethod
    def _resolve_variant(product: Product, item: OrderLineCreate) -> ProductVariant | None:
        if not product.variants:
            return None
        matches = [
            variant
            for variant in product.variants
            if (variant.size or "") == item.size and (variant.color or "") == item.color
        ]
        if len(matches) != 1:
            raise OrderCatalogItemError("Order contains an unavailable product variant")
        return matches[0]

    @staticmethod
    def _request_fingerprint(
        command: OrderCreationCommand,
        *,
        user_id: int | None,
        guest_access_digest: str | None = None,
    ) -> str:
        canonical = {
            "user_id": user_id,
            "guest_access_digest": guest_access_digest,
            "command": command.model_dump(mode="json"),
        }
        return hashlib.sha256(
            json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _result(order: Order, *, replayed: bool) -> OrderCreationResult:
        return OrderCreationResult(
            order_id=order.id,
            replayed=replayed,
            status=order.status,
            payment_status=order.payment_status,
            items_subtotal=order.items_subtotal,
            delivery_price=order.delivery_price,
            total_price=order.total_price,
            currency=order.currency,
            version=order.version,
        )


class OrderLifecycleService:
    def __init__(
        self,
        settings: Settings | None = None,
        repository: OrderRepository | None = None,
        inventory_service: InventoryReservationService | None = None,
        inventory_repository: InventoryRepository | None = None,
        fulfillment_service: FulfillmentOutboxService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or OrderRepository()
        self.inventory_repository = inventory_repository or InventoryRepository()
        self.inventory_service = inventory_service or InventoryReservationService(
            self.settings,
            self.inventory_repository,
        )
        self.fulfillment_service = fulfillment_service or FulfillmentOutboxService(self.settings)

    async def confirm_payment(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        payment_attempt_id: int | None = None,
        now: datetime | None = None,
    ) -> Order:
        order = await self._order_for_update(session, order_id)
        if order.payment_status == OrderPaymentStatus.PAID.value and order.status in {
            OrderStatus.PROCESSING.value,
            OrderStatus.SHIPPED.value,
            OrderStatus.COMPLETED.value,
        }:
            await self.inventory_service.confirm_order(session, order=order, now=now)
            await self.fulfillment_service.schedule_paid_order(
                session,
                order=order,
                payment_attempt_id=payment_attempt_id,
                now=now,
            )
            return order
        self._require_state(
            order,
            status=OrderStatus.NEW,
            payment_status=OrderPaymentStatus.PENDING,
        )
        await self.inventory_service.confirm_order(session, order=order, now=now)
        order.payment_status = OrderPaymentStatus.PAID.value
        self._transition(
            session,
            order=order,
            to_status=OrderStatus.PROCESSING,
            reason_code="payment.confirmed",
        )
        await self.fulfillment_service.schedule_paid_order(
            session,
            order=order,
            payment_attempt_id=payment_attempt_id,
            now=now,
        )
        await session.flush()
        return order

    async def cancel_pending(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        reason_code: str,
        now: datetime | None = None,
    ) -> Order:
        order = await self._order_for_update(session, order_id)
        if order.status == OrderStatus.CANCELLED.value:
            await self.inventory_service.release_order(
                session,
                order=order,
                reason=reason_code,
                now=now,
            )
            return order
        self._require_state(
            order,
            status=OrderStatus.NEW,
            payment_status=OrderPaymentStatus.PENDING,
        )
        await self.inventory_service.release_order(
            session,
            order=order,
            reason=reason_code,
            now=now,
        )
        order.payment_status = OrderPaymentStatus.FAILED.value
        self._transition(
            session,
            order=order,
            to_status=OrderStatus.CANCELLED,
            reason_code=reason_code,
        )
        await session.flush()
        return order

    async def mark_shipped(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        actor_user_id: int,
    ) -> Order:
        order = await self._order_for_update(session, order_id)
        self._require_state(
            order,
            status=OrderStatus.PROCESSING,
            payment_status=OrderPaymentStatus.PAID,
        )
        self._transition(
            session,
            order=order,
            to_status=OrderStatus.SHIPPED,
            reason_code="delivery.shipped",
            actor_user_id=actor_user_id,
        )
        await session.flush()
        return order

    async def mark_completed(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        actor_user_id: int,
    ) -> Order:
        order = await self._order_for_update(session, order_id)
        self._require_state(
            order,
            status=OrderStatus.SHIPPED,
            payment_status=OrderPaymentStatus.PAID,
        )
        self._transition(
            session,
            order=order,
            to_status=OrderStatus.COMPLETED,
            reason_code="delivery.completed",
            actor_user_id=actor_user_id,
        )
        await session.flush()
        return order

    async def expire_pending(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        batch_size: int = 100,
    ) -> int:
        if not 1 <= batch_size <= 1_000:
            raise ValueError("Reservation expiry batch size must be between 1 and 1000")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        orders = await self.inventory_repository.list_expired_orders_for_update(
            session,
            now=current_time,
            limit=batch_size,
        )
        for order in orders:
            self._require_state(
                order,
                status=OrderStatus.NEW,
                payment_status=OrderPaymentStatus.PENDING,
            )
            await self.inventory_service.release_order(
                session,
                order=order,
                reason="reservation.expired",
                expired=True,
                now=current_time,
            )
            order.payment_status = OrderPaymentStatus.FAILED.value
            self._transition(
                session,
                order=order,
                to_status=OrderStatus.CANCELLED,
                reason_code="reservation.expired",
            )
        await session.flush()
        return len(orders)

    async def _order_for_update(self, session: AsyncSession, order_id: int) -> Order:
        order = await self.repository.get_order_for_update(session, order_id=order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    @staticmethod
    def _require_state(
        order: Order,
        *,
        status: OrderStatus,
        payment_status: OrderPaymentStatus,
    ) -> None:
        if order.status != status.value or order.payment_status != payment_status.value:
            raise InvalidOrderTransitionError(
                f"Order cannot transition from {order.status}/{order.payment_status}"
            )

    @staticmethod
    def _transition(
        session: AsyncSession,
        *,
        order: Order,
        to_status: OrderStatus,
        reason_code: str,
        actor_user_id: int | None = None,
    ) -> None:
        previous = order.status
        order.version += 1
        order.status = to_status.value
        session.add(
            OrderStatusHistory(
                order_id=order.id,
                version=order.version,
                from_status=previous,
                to_status=to_status.value,
                reason_code=reason_code[:64],
                actor_user_id=actor_user_id,
                details={},
            )
        )


class OrderOwnershipBridgeService:
    def __init__(
        self,
        reader: LegacyOrderReader,
        security: OtpSecurity,
        *,
        repository: LegacyOrderClaimRepository | None = None,
    ) -> None:
        self.reader = reader
        self.security = security
        self.repository = repository or LegacyOrderClaimRepository()

    async def list_owned_orders(
        self,
        session: AsyncSession,
        *,
        user: User,
    ) -> list[LegacyOrderResponse]:
        if (
            user.status == UserStatus.ACTIVE.value
            and user.email
            and user.email_normalized
            and user.email_verified_at is not None
        ):
            matching_ids = await to_thread.run_sync(
                self.reader.find_order_ids_by_verified_email,
                user.email_normalized,
            )
            identifier_digest = self.security.digest_client_value(user.email_normalized)
            if identifier_digest is None:
                raise RuntimeError("Verified email digest is unavailable")
            await self.repository.claim_verified_email_orders(
                session,
                user_id=user.id,
                legacy_order_ids=matching_ids,
                identifier_digest=identifier_digest,
            )
            await session.flush()

        claimed_ids = await self.repository.list_claimed_order_ids(
            session,
            user_id=user.id,
        )
        raw_orders = await to_thread.run_sync(self.reader.get_orders, claimed_ids)
        return [LegacyOrderResponse.model_validate(order) for order in raw_orders]


class TargetOrderReadService:
    def __init__(
        self,
        security: OtpSecurity,
        *,
        repository: TargetOrderReadRepository | None = None,
        claim_repository: LegacyOrderClaimRepository | None = None,
    ) -> None:
        self.security = security
        self.repository = repository or TargetOrderReadRepository()
        self.claim_repository = claim_repository or LegacyOrderClaimRepository()

    async def list_owned_orders(
        self,
        session: AsyncSession,
        *,
        user: User,
    ) -> list[LegacyOrderResponse]:
        await self._claim_verified_imports(session, user=user)
        orders = await self.repository.list_owned(session, user_id=user.id)
        return [self.map_order(order) for order in orders]

    async def get_owned_order(
        self,
        session: AsyncSession,
        *,
        user: User,
        order_id: int,
    ) -> LegacyOrderResponse | None:
        await self._claim_verified_imports(session, user=user)
        order = await self.repository.get_owned(
            session,
            order_id=order_id,
            user_id=user.id,
        )
        return self.map_order(order) if order is not None else None

    async def list_all_orders(
        self,
        session: AsyncSession,
        *,
        limit: int,
        offset: int,
    ) -> list[LegacyOrderResponse]:
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("Invalid order pagination")
        orders = await self.repository.list_all(
            session,
            limit=limit,
            offset=offset,
        )
        return [self.map_order(order) for order in orders]

    async def get_order(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> LegacyOrderResponse | None:
        order = await self.repository.get(session, order_id=order_id)
        return self.map_order(order) if order is not None else None

    async def _claim_verified_imports(
        self,
        session: AsyncSession,
        *,
        user: User,
    ) -> None:
        if (
            user.status != UserStatus.ACTIVE.value
            or not user.email_normalized
            or user.email_verified_at is None
        ):
            return
        matching_ids = await self.repository.find_imported_ids_by_verified_email(
            session,
            email_normalized=user.email_normalized,
        )
        identifier_digest = self.security.digest_client_value(user.email_normalized)
        if identifier_digest is None:
            raise RuntimeError("Verified email digest is unavailable")
        await self.claim_repository.claim_verified_email_orders(
            session,
            user_id=user.id,
            legacy_order_ids=matching_ids,
            identifier_digest=identifier_digest,
        )
        await session.flush()

    @staticmethod
    def map_order(order: Order) -> LegacyOrderResponse:
        imported = order.legacy_import
        cart_items = (
            imported.raw_cart_items
            if imported is not None
            else json.dumps(
                [TargetOrderReadService._item_payload(item) for item in order.items],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return LegacyOrderResponse(
            id=order.id,
            email=order.email,
            phone=order.phone,
            first_name=order.first_name,
            last_name=order.last_name,
            patronymic=order.patronymic,
            delivery_city=order.delivery_city,
            delivery_method=order.delivery_method,
            delivery_address=order.delivery_address,
            payment_method=order.payment_method,
            cart_items=cart_items,
            total_price=float(order.total_price),
            status=order.status,
            cdek_uuid=(imported.delivery_provider_uuid if imported is not None else None),
            cdek_point_code=order.cdek_point_code,
            delivery_price=float(order.delivery_price),
            payment_id=(imported.payment_provider_id if imported is not None else None),
            payment_status=order.payment_status,
            created_at=order.created_at,
            cdek_number=(imported.delivery_provider_number if imported is not None else None),
            cdek_status=(imported.delivery_provider_status if imported is not None else None),
        )

    @staticmethod
    def _item_payload(item: OrderItem) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": item.client_item_id,
            "product_id": item.product_id_snapshot,
            "title": item.title_snapshot,
            "price": float(item.unit_price),
            "image": item.image_url_snapshot,
            "size": item.size_snapshot,
            "color": item.color_snapshot,
            "quantity": item.quantity,
        }
        if item.variant_id_snapshot is not None:
            payload["variant_id"] = item.variant_id_snapshot
        if item.sku_snapshot is not None:
            payload["sku"] = item.sku_snapshot
        if item.customization_snapshot is not None:
            payload["customization"] = item.customization_snapshot
        return payload
