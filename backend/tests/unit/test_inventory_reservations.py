from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.service import (
    CatalogInventoryReservedError,
    CatalogService,
    CatalogWriteService,
)
from app.modules.identity.models import User, UserStatus
from app.modules.inventory.models import InventoryReservation
from app.modules.inventory.service import (
    InventoryReservationExpiredError,
    InventoryReservationService,
)
from app.modules.orders.models import Order, OrderStatusHistory
from app.modules.orders.schemas import OrderCreationCommand
from app.modules.orders.service import (
    InvalidOrderTransitionError,
    OrderCreationService,
    OrderLifecycleService,
)


def _settings(path: Path, *, ttl_seconds: int = 1_800) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        inventory_reservation_ttl_seconds=ttl_seconds,
    )


async def _seed(database: DatabaseManager) -> tuple[int, int, int]:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        product = Product(
            title="Reserved product",
            price=Decimal("100.00"),
            is_active=True,
            stock_quantity=5,
            sizes=["M"],
            colors=["black"],
            weight_kg=Decimal("0.500"),
            height_cm=Decimal("10.00"),
            width_cm=Decimal("20.00"),
            length_cm=Decimal("30.00"),
        )
        product.variants.append(
            ProductVariant(
                size="M",
                color="black",
                sku="RES-M-BLACK",
                stock_quantity=4,
            )
        )
        manager = User(
            email="manager@example.test",
            email_normalized="manager@example.test",
            status=UserStatus.ACTIVE.value,
        )
        session.add_all([product, manager])
        await session.commit()
        return product.id, product.variants[0].id, manager.id


def _command(product_id: int) -> OrderCreationCommand:
    return OrderCreationCommand.model_validate(
        {
            "email": "customer@example.test",
            "phone": "+7 900 000-00-00",
            "first_name": "Customer",
            "delivery_city": "Moscow",
            "delivery_method": "cdek_pickup",
            "delivery_address": "Pickup point",
            "cdek_point_code": "MSK1",
            "payment_method": "card",
            "items": [
                {
                    "id": "reserved-line",
                    "product_id": product_id,
                    "title": "Client title",
                    "price": "1.00",
                    "size": "M",
                    "color": "black",
                    "quantity": 2,
                }
            ],
            "claimed_total_price": "225.00",
            "delivery_price": "25.00",
        }
    )


def test_payment_confirmation_consumes_reservation_and_state_machine(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "confirmed.db")
        database = DatabaseManager(settings)
        await database.startup()
        now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        try:
            product_id, variant_id, manager_id = await _seed(database)
            async with database.session() as session:
                created = await OrderCreationService(settings).create(
                    session,
                    idempotency_key="confirmed_attempt_0001",
                    command=_command(product_id),
                    now=now,
                )
                await session.commit()

            async with database.session() as session:
                catalog_product = await CatalogService(CatalogResponseMapper(settings)).get_product(
                    session, product_id
                )
                assert catalog_product is not None
                assert catalog_product.stock_quantity == 3
                assert catalog_product.variants[0].stock_quantity == 2

            lifecycle = OrderLifecycleService(settings)
            async with database.session() as session:
                order = await lifecycle.confirm_payment(
                    session,
                    order_id=created.order_id,
                    now=now + timedelta(seconds=10),
                )
                await session.commit()
                assert order.status == "processing"
                assert order.payment_status == "paid"

            async with database.session() as session:
                replay = await lifecycle.confirm_payment(
                    session,
                    order_id=created.order_id,
                    now=now + timedelta(seconds=11),
                )
                await session.commit()
                assert replay.version == 2

            async with database.session() as session:
                await lifecycle.mark_shipped(
                    session,
                    order_id=created.order_id,
                    actor_user_id=manager_id,
                )
                await lifecycle.mark_completed(
                    session,
                    order_id=created.order_id,
                    actor_user_id=manager_id,
                )
                await session.commit()

            async with database.session() as session:
                completed_replay = await lifecycle.confirm_payment(
                    session,
                    order_id=created.order_id,
                    now=now + timedelta(seconds=12),
                )
                await session.commit()
                assert completed_replay.status == "completed"
                assert completed_replay.version == 4

            with pytest.raises(InvalidOrderTransitionError):
                async with database.session() as session:
                    await lifecycle.cancel_pending(
                        session,
                        order_id=created.order_id,
                        reason_code="customer.cancelled",
                    )

            async with database.session() as session:
                product = await session.get(Product, product_id)
                variant = await session.get(ProductVariant, variant_id)
                reservation = await session.scalar(select(InventoryReservation))
                order = await session.get(Order, created.order_id)
                history = list(
                    await session.scalars(
                        select(OrderStatusHistory).order_by(OrderStatusHistory.version)
                    )
                )
                assert product is not None and product.stock_quantity == 3
                assert product.reserved_quantity == 0
                assert variant is not None and variant.stock_quantity == 2
                assert variant.reserved_quantity == 0
                assert reservation is not None and reservation.status == "confirmed"
                assert reservation.resolution_reason == "payment.confirmed"
                assert order is not None and order.status == "completed" and order.version == 4
                assert [event.to_status for event in history] == [
                    "new",
                    "processing",
                    "shipped",
                    "completed",
                ]
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_expiry_releases_stock_and_catalog_writes_are_guarded(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "expired.db", ttl_seconds=60)
        database = DatabaseManager(settings)
        await database.startup()
        now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        try:
            product_id, variant_id, manager_id = await _seed(database)
            async with database.session() as session:
                created = await OrderCreationService(settings).create(
                    session,
                    idempotency_key="expired_attempt_0001",
                    command=_command(product_id),
                    now=now,
                )
                await session.commit()

            with pytest.raises(CatalogInventoryReservedError):
                async with database.session() as session:
                    await CatalogWriteService(settings).delete_product(
                        session,
                        product_id=product_id,
                        actor_user_id=manager_id,
                    )

            lifecycle = OrderLifecycleService(settings)
            with pytest.raises(InventoryReservationExpiredError):
                async with database.session() as session:
                    await lifecycle.confirm_payment(
                        session,
                        order_id=created.order_id,
                        now=now + timedelta(seconds=61),
                    )

            async with database.session() as session:
                assert (
                    await lifecycle.expire_pending(
                        session,
                        now=now + timedelta(seconds=61),
                        batch_size=10,
                    )
                    == 1
                )
                await session.commit()
            async with database.session() as session:
                assert (
                    await lifecycle.expire_pending(
                        session,
                        now=now + timedelta(seconds=62),
                        batch_size=10,
                    )
                    == 0
                )
                await session.commit()

            async with database.session() as session:
                product = await session.get(Product, product_id)
                variant = await session.get(ProductVariant, variant_id)
                reservation = await session.scalar(select(InventoryReservation))
                order = await session.get(Order, created.order_id)
                assert product is not None and product.stock_quantity == 5
                assert product.reserved_quantity == 0
                assert variant is not None and variant.stock_quantity == 4
                assert variant.reserved_quantity == 0
                assert reservation is not None and reservation.status == "expired"
                assert reservation.resolution_reason == "reservation.expired"
                assert order is not None and order.status == "cancelled"
                assert order.payment_status == "failed" and order.version == 2
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_active_reservation_refresh_is_bounded_and_versioned(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "refreshed.db", ttl_seconds=60)
        database = DatabaseManager(settings)
        await database.startup()
        now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        try:
            product_id, _, _ = await _seed(database)
            async with database.session() as session:
                created = await OrderCreationService(settings).create(
                    session,
                    idempotency_key="refreshed_attempt_0001",
                    command=_command(product_id),
                    now=now,
                )
                await session.commit()

            service = InventoryReservationService(settings)
            retry_time = now + timedelta(seconds=30)
            async with database.session() as session:
                refreshed_until = await service.refresh_active_order(
                    session,
                    order_id=created.order_id,
                    now=retry_time,
                )
                await session.commit()
            assert refreshed_until == now + timedelta(seconds=90)

            async with database.session() as session:
                unchanged_until = await service.refresh_active_order(
                    session,
                    order_id=created.order_id,
                    now=retry_time,
                )
                await session.commit()
                reservation = await session.scalar(select(InventoryReservation))
                assert reservation is not None
                assert reservation.expires_at.replace(tzinfo=timezone.utc) == refreshed_until
                assert reservation.version == 2
            assert unchanged_until == refreshed_until

            with pytest.raises(InventoryReservationExpiredError):
                async with database.session() as session:
                    await service.refresh_active_order(
                        session,
                        order_id=created.order_id,
                        now=now + timedelta(seconds=91),
                    )
        finally:
            await database.shutdown()

    asyncio.run(scenario())
