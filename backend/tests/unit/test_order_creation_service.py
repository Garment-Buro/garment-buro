from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product, ProductVariant
from app.modules.inventory.models import InventoryReservation
from app.modules.inventory.service import InsufficientStockError
from app.modules.orders.models import (
    Order,
    OrderCreationRequest,
    OrderGuestAccess,
    OrderItem,
    OrderStatusHistory,
)
from app.modules.orders.schemas import OrderCreationCommand
from app.modules.orders.security import (
    InvalidOrderIdempotencyKeyError,
    digest_order_guest_access_token,
    digest_order_idempotency_key,
    generate_order_guest_access_token,
)
from app.modules.orders.service import (
    OrderCatalogItemError,
    OrderCreationService,
    OrderIdempotencyConflictError,
    OrderTotalMismatchError,
)


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
    )


def _command(
    product_id: int,
    *,
    claimed_total_price: Decimal = Decimal("250.50"),
    size: str = "M",
    color: str = "black",
    quantity: int = 2,
    delivery_address: str = "Moscow pickup point",
) -> OrderCreationCommand:
    return OrderCreationCommand.model_validate(
        {
            "email": "Customer@Example.TEST",
            "phone": "+7 900 000-00-00",
            "first_name": "Customer",
            "delivery_city": "Moscow",
            "delivery_method": "cdek_pickup",
            "delivery_address": delivery_address,
            "cdek_point_code": "MSK123",
            "payment_method": "card",
            "items": [
                {
                    "id": "cart-line-1",
                    "product_id": product_id,
                    "title": "Untrusted client title",
                    "price": "1.00",
                    "image": "/uploads/snapshot.webp",
                    "size": size,
                    "color": color,
                    "quantity": quantity,
                    "customization": {"fit": {"lengthCm": 70, "widthCm": 58}},
                }
            ],
            "claimed_total_price": claimed_total_price,
            "delivery_price": "50.00",
        }
    )


async def _seed_catalog(database: DatabaseManager) -> tuple[int, int]:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        product = Product(
            title="Server catalog title",
            price=Decimal("100.25"),
            is_active=True,
            stock_quantity=7,
            sizes=["M"],
            colors=["black"],
            weight_kg=Decimal("0.425"),
            height_cm=Decimal("9.10"),
            width_cm=Decimal("21.20"),
            length_cm=Decimal("30.30"),
        )
        product.variants.append(
            ProductVariant(
                size="M",
                color="black",
                sku="SKU-M-BLACK",
                stock_quantity=5,
            )
        )
        session.add(product)
        await session.commit()
        return product.id, product.variants[0].id


def test_order_creation_is_idempotent_and_snapshots_server_catalog(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "order.db")
        database = DatabaseManager(settings)
        await database.startup()
        idempotency_key = "checkout_attempt_0001"
        try:
            product_id, variant_id = await _seed_catalog(database)
            command = _command(product_id)
            service = OrderCreationService(settings)
            guest_access_token = generate_order_guest_access_token()

            async with database.session() as session:
                created = await service.create(
                    session,
                    idempotency_key=idempotency_key,
                    command=command,
                    guest_access_token=guest_access_token,
                )
                await session.commit()
                assert not created.replayed
                assert created.items_subtotal == Decimal("200.50")
                assert created.total_price == Decimal("250.50")

            async with database.session() as session:
                replayed = await service.create(
                    session,
                    idempotency_key=idempotency_key,
                    command=command,
                    guest_access_token=guest_access_token,
                )
                await session.commit()
                assert replayed.replayed
                assert replayed.order_id == created.order_id

            with pytest.raises(OrderIdempotencyConflictError):
                async with database.session() as session:
                    await service.create(
                        session,
                        idempotency_key=idempotency_key,
                        command=command,
                        guest_access_token=generate_order_guest_access_token(),
                    )

            async with database.session() as session:
                assert int(await session.scalar(select(func.count()).select_from(Order)) or 0) == 1
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(OrderCreationRequest))
                        or 0
                    )
                    == 1
                )
                order = await session.scalar(select(Order))
                item = await session.scalar(select(OrderItem))
                history = await session.scalar(select(OrderStatusHistory))
                product = await session.get(Product, product_id)
                request = await session.scalar(select(OrderCreationRequest))
                reservation = await session.scalar(select(InventoryReservation))
                guest_access = await session.scalar(select(OrderGuestAccess))
                variant = await session.get(ProductVariant, variant_id)
                assert order is not None and item is not None and history is not None
                assert order.email_normalized == "customer@example.test"
                assert order.request_fingerprint_sha256 == request.request_fingerprint_sha256
                assert item.product_id_snapshot == product_id
                assert item.variant_id_snapshot == variant_id
                assert item.sku_snapshot == "SKU-M-BLACK"
                assert item.title_snapshot == "Server catalog title"
                assert item.unit_price == Decimal("100.25")
                assert item.line_total == Decimal("200.50")
                assert item.customization_snapshot == {"fit": {"lengthCm": 70, "widthCm": 58}}
                assert item.delivery_weight_kg_snapshot == Decimal("0.425")
                assert item.delivery_height_cm_snapshot == Decimal("9.10")
                assert item.delivery_width_cm_snapshot == Decimal("21.20")
                assert item.delivery_length_cm_snapshot == Decimal("30.30")
                assert history.from_status is None
                assert history.to_status == "new"
                assert history.reason_code == "order.created"
                assert product is not None and product.stock_quantity == 7
                assert product.reserved_quantity == 2
                assert variant is not None and variant.stock_quantity == 5
                assert variant.reserved_quantity == 2
                assert reservation is not None and reservation.status == "active"
                assert reservation.quantity == 2
                assert guest_access is not None
                assert guest_access.token_digest_sha256 == digest_order_guest_access_token(
                    guest_access_token
                )
                assert guest_access_token not in repr(guest_access.__dict__)
                assert request is not None
                assert request.key_digest_sha256 == digest_order_idempotency_key(idempotency_key)
                assert idempotency_key not in repr(request.__dict__)
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_order_creation_rejects_key_reuse_total_tampering_and_unknown_variant(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "order-errors.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            product_id, _ = await _seed_catalog(database)
            service = OrderCreationService(settings)
            key = "checkout_attempt_0002"
            async with database.session() as session:
                await service.create(
                    session,
                    idempotency_key=key,
                    command=_command(product_id),
                )
                await session.commit()

            with pytest.raises(OrderIdempotencyConflictError):
                async with database.session() as session:
                    await service.create(
                        session,
                        idempotency_key=key,
                        command=_command(product_id, delivery_address="Another address"),
                    )

            with pytest.raises(OrderTotalMismatchError):
                async with database.session() as session:
                    await service.create(
                        session,
                        idempotency_key="checkout_attempt_0003",
                        command=_command(
                            product_id,
                            claimed_total_price=Decimal("1.00"),
                        ),
                    )

            with pytest.raises(OrderCatalogItemError, match="variant"):
                async with database.session() as session:
                    await service.create(
                        session,
                        idempotency_key="checkout_attempt_0004",
                        command=_command(product_id, size="XL"),
                    )

            with pytest.raises(InsufficientStockError):
                async with database.session() as session:
                    await service.create(
                        session,
                        idempotency_key="checkout_attempt_0005",
                        command=_command(
                            product_id,
                            quantity=6,
                            claimed_total_price=Decimal("651.50"),
                        ),
                    )

            duplicate_variant_lines = _command(product_id).model_dump(mode="json")
            duplicate_variant_lines["items"] = [
                {
                    **duplicate_variant_lines["items"][0],
                    "id": "cart-line-aggregate-1",
                },
                {
                    **duplicate_variant_lines["items"][0],
                    "id": "cart-line-aggregate-2",
                },
            ]
            duplicate_variant_lines["claimed_total_price"] = "451.00"
            with pytest.raises(InsufficientStockError):
                async with database.session() as session:
                    await service.create(
                        session,
                        idempotency_key="checkout_attempt_0006",
                        command=OrderCreationCommand.model_validate(duplicate_variant_lines),
                    )

            async with database.session() as session:
                assert int(await session.scalar(select(func.count()).select_from(Order)) or 0) == 1
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(OrderCreationRequest))
                        or 0
                    )
                    == 1
                )
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(InventoryReservation))
                        or 0
                    )
                    == 1
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_order_creation_validates_item_identity_and_idempotency_key(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="unique"):
        OrderCreationCommand.model_validate(
            {
                **_command(1).model_dump(mode="json"),
                "items": [
                    _command(1).items[0].model_dump(mode="json"),
                    _command(1).items[0].model_dump(mode="json"),
                ],
            }
        )

    async def scenario() -> None:
        settings = _settings(tmp_path / "invalid-key.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            product_id, _ = await _seed_catalog(database)
            with pytest.raises(InvalidOrderIdempotencyKeyError):
                async with database.session() as session:
                    await OrderCreationService(settings).create(
                        session,
                        idempotency_key="short",
                        command=_command(product_id),
                    )
            async with database.session() as session:
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(OrderCreationRequest))
                        or 0
                    )
                    == 0
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cdek_order_requires_trusted_logistics_measurements(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "cdek-logistics.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            product_id, _ = await _seed_catalog(database)
            async with database.session() as session:
                product = await session.get(Product, product_id)
                assert product is not None
                product.weight_kg = Decimal("0")
                await session.commit()

            with pytest.raises(OrderCatalogItemError, match="logistics"):
                async with database.session() as session:
                    await OrderCreationService(settings).create(
                        session,
                        idempotency_key="checkout_missing_cdek_logistics",
                        command=_command(product_id),
                    )

            async with database.session() as session:
                assert int(await session.scalar(select(func.count()).select_from(Order)) or 0) == 0
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(OrderCreationRequest))
                        or 0
                    )
                    == 0
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())
