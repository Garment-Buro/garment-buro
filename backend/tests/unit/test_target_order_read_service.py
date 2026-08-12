from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.models import User, UserStatus
from app.modules.identity.security import OtpSecurity
from app.modules.orders.models import Order, OrderItem, OrderStatusHistory
from app.modules.orders.service import TargetOrderReadService


def test_target_order_read_mapper_preserves_new_order_cart_contract(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'orders.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                user = User(
                    email="owner@example.test",
                    email_normalized="owner@example.test",
                    status=UserStatus.ACTIVE.value,
                    email_verified_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
                )
                session.add(user)
                await session.flush()
                order = Order(
                    user_id=user.id,
                    email=user.email,
                    email_normalized=user.email_normalized,
                    phone="+79000000000",
                    first_name="Owner",
                    delivery_city="Moscow",
                    delivery_method="pickup",
                    delivery_address="Showroom",
                    payment_method="card",
                    items_subtotal=Decimal("300.00"),
                    delivery_price=Decimal("0.00"),
                    total_price=Decimal("300.00"),
                    status="new",
                    payment_status="pending",
                    version=1,
                    request_fingerprint_sha256="f" * 64,
                )
                order.items.append(
                    OrderItem(
                        client_item_id="direct-line",
                        product_id_snapshot=5,
                        variant_id_snapshot=8,
                        sku_snapshot="SKU-8",
                        title_snapshot="Direct item",
                        unit_price=Decimal("150.00"),
                        quantity=2,
                        line_total=Decimal("300.00"),
                        image_url_snapshot="/uploads/direct.webp",
                        size_snapshot="M",
                        color_snapshot="black",
                        customization_snapshot={"fit": {"lengthCm": 70}},
                        sort_order=0,
                    )
                )
                order.status_history.append(
                    OrderStatusHistory(
                        version=1,
                        from_status=None,
                        to_status="new",
                        reason_code="order.created",
                        details={},
                    )
                )
                session.add(order)
                await session.commit()

            service = TargetOrderReadService(OtpSecurity("p" * 32))
            async with database.session() as session:
                user = await session.get(User, user.id)
                assert user is not None
                owned = await service.list_owned_orders(session, user=user)
                assert len(owned) == 1
                payload = json.loads(owned[0].cart_items or "[]")
                assert payload == [
                    {
                        "id": "direct-line",
                        "product_id": 5,
                        "title": "Direct item",
                        "price": 150.0,
                        "image": "/uploads/direct.webp",
                        "size": "M",
                        "color": "black",
                        "quantity": 2,
                        "variant_id": 8,
                        "sku": "SKU-8",
                        "customization": {"fit": {"lengthCm": 70}},
                    }
                ]
        finally:
            await database.shutdown()

    asyncio.run(scenario())
