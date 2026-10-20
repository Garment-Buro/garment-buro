from __future__ import annotations

import asyncio
import sqlite3
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.session import DatabaseManager
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import Order, OrderCreationRequest
from app.modules.orders.security import generate_order_guest_access_token
from app.modules.payments.models import PaymentAttempt
from tests.contract.test_checkout_api import CheckoutProvider, _application, _command, _headers


def test_changed_price_can_be_confirmed_without_reverting_catalog(tmp_path: Path) -> None:
    provider = CheckoutProvider()
    application, target_database, product_id, quote = _application(tmp_path, provider)
    guest_token = generate_order_guest_access_token()
    with sqlite3.connect(tmp_path / "target.db") as connection:
        connection.execute("UPDATE products SET price=150.25")

    async def counts() -> list[int]:
        database = DatabaseManager(target_database.settings)
        await database.startup()
        try:
            async with database.session() as session:
                return [
                    int(await session.scalar(select(func.count()).select_from(model)) or 0)
                    for model in (Order, OrderCreationRequest, InventoryReservation, PaymentAttempt)
                ]
        finally:
            await database.shutdown()

    with TestClient(application) as client:
        rejected = client.post(
            "/api/orders",
            json=_command(product_id, quote=quote),
            headers=_headers(guest_token=guest_token, key="checkout_price_original"),
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"] == {
            "code": "checkout_price_changed",
            "currency": "RUB",
            "prices": [{"id": "checkout-line-1", "product_id": product_id, "price": 150.25}],
        }
        assert rejected.headers["cache-control"] == "no-store"
        assert provider.calls == []
        assert asyncio.run(counts()) == [0, 0, 0, 0]
        command = _command(product_id, quote=quote, claimed_total_price="350.50")
        command["items"][0]["price"] = "150.25"
        confirmed = client.post(
            "/api/orders",
            json=command,
            headers=_headers(guest_token=guest_token, key="checkout_price_confirmed"),
        )
        assert confirmed.status_code == 200
        stored = client.get(
            "/api/order-access",
            headers={"X-Order-Access-Token": guest_token},
        )
        assert stored.status_code == 200
        assert stored.json()["id"] == confirmed.json()["order_id"]
        assert Decimal(str(stored.json()["total_price"])) == Decimal("350.50")
    assert len(provider.calls) == 1
    assert asyncio.run(counts()) == [1, 1, 1, 1]
