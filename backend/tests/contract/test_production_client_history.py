import asyncio
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from app.modules.orders.models import Order
from app.modules.production.client_schemas import ClientHistoryQuery
from app.modules.production.client_service import ProductionClientService
from app.modules.production.inbox_models import AdminInboxItem
from tests.unit.test_production_admin import admin_app


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
def test_client_history_reaches_every_order_and_linked_ticket_without_loading_bodies(
    tmp_path, dialect
):
    postgres_url = os.getenv("PRODUCTION_TEST_POSTGRES_URL") if dialect == "postgresql" else None
    if dialect == "postgresql" and not postgres_url:
        pytest.skip("Isolated PostgreSQL CI required")

    async def scenario():
        async with admin_app(tmp_path, postgres_url=postgres_url) as (app, db, code, cutter):
            at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            async with db.session() as session:
                session.add_all(
                    [
                        Order(
                            id=1000 + i,
                            request_fingerprint_sha256=f"{1000 + i:064x}",
                            user_id=3,
                            first_name="Клиент",
                            phone="+70000000000",
                            email="shared@example.test",
                            email_normalized="shared@example.test",
                            items_subtotal=Decimal("10"),
                            delivery_price=Decimal("0"),
                            total_price=Decimal("10"),
                            created_at=at,
                        )
                        for i in range(130)
                    ]
                )
                session.add_all(
                    [
                        Order(
                            id=3000,
                            request_fingerprint_sha256=f"{3000:064x}",
                            user_id=3,
                            first_name="Демо",
                            phone="+70000000000",
                            items_subtotal=Decimal("999"),
                            delivery_price=Decimal("0"),
                            total_price=Decimal("999"),
                            is_demo=True,
                        ),
                        Order(
                            id=3001,
                            request_fingerprint_sha256=f"{3001:064x}",
                            user_id=2,
                            first_name="Другой",
                            phone="+70000000000",
                            email="shared@example.test",
                            email_normalized="shared@example.test",
                            items_subtotal=Decimal("999"),
                            delivery_price=Decimal("0"),
                            total_price=Decimal("999"),
                        ),
                    ]
                )
                await session.flush()
                session.add_all(
                    [
                        AdminInboxItem(
                            id=1000 + i,
                            kind="support",
                            subject=f"Тикет {i}",
                            message="Содержимое не должно попадать в список",
                            reporter_user_id=3,
                            created_at=at,
                            updated_at=at,
                        )
                        for i in range(130)
                    ]
                )
                session.add_all(
                    [
                        AdminInboxItem(
                            id=3000,
                            kind="support",
                            subject="Старый заказ",
                            message="Приватное тело",
                            order_id=1000,
                            created_at=at - timedelta(days=1),
                            updated_at=at - timedelta(days=1),
                        ),
                        AdminInboxItem(
                            id=3001,
                            kind="support",
                            subject="Другой клиент",
                            message="Чужой текст",
                            order_id=3001,
                        ),
                        AdminInboxItem(
                            id=3002,
                            kind="production_problem",
                            subject="Не поддержка",
                            message="Текст",
                            reporter_user_id=3,
                        ),
                    ]
                )
                await session.commit()
            statements = []

            def capture(_connection, _cursor, statement, _parameters, _context, _many):
                if statement.lstrip().upper().startswith("SELECT"):
                    statements.append(statement)

            event.listen(db.engine.sync_engine, "before_cursor_execute", capture)
            try:
                async with AsyncClient(
                    transport=ASGITransport(app), base_url="https://test"
                ) as client:
                    await client.post("/api/production/auth/login", json={"code": code})
                    profile = await client.get(
                        "/api/production/admin/clients/detail", params={"key": "user:3"}
                    )
                    assert profile.status_code == 200, profile.text
                    detail = profile.json()
                    assert "orders" not in detail and "tickets" not in detail
                    assert detail["orders_count"] == 131 and detail["tickets_count"] == 132
                    cursors = {}
                    for kind, count in [("orders", 131), ("tickets", 132)]:
                        items = []
                        cursor = None
                        while True:
                            response = await client.get(
                                f"/api/production/admin/clients/{kind}",
                                params={
                                    "key": "user:3",
                                    "limit": 24,
                                    **({"cursor": cursor} if cursor else {}),
                                },
                            )
                            assert response.status_code == 200, response.text
                            assert response.headers["cache-control"] == "no-store"
                            page = response.json()
                            assert len(page["items"]) <= 24
                            items.extend(page["items"])
                            cursor = page["next_cursor"]
                            if not cursor:
                                break
                            cursors.setdefault(kind, cursor)
                        assert len(items) == count and len({item["id"] for item in items}) == count
                        assert 1000 in {item["id"] for item in items}
                        assert 3001 not in {item["id"] for item in items}
                        if kind == "tickets":
                            assert 3000 in {item["id"] for item in items}
                            assert all("message" not in item for item in items)
                    for kind, key, cursor in [
                        ("orders", "user:2", cursors["orders"]),
                        ("tickets", "user:3", cursors["orders"]),
                        ("orders", "user:3", "not-a-cursor"),
                    ]:
                        bad = await client.get(
                            f"/api/production/admin/clients/{kind}",
                            params={"key": key, "cursor": cursor},
                        )
                        assert (
                            bad.status_code == 422
                            and bad.json()["detail"]["code"] == "invalid_cursor"
                        )
                        assert bad.headers["cache-control"] == "no-store"
                    assert (
                        await client.get(
                            "/api/production/admin/clients/orders",
                            params={"key": "user:999999999999999999999"},
                        )
                    ).status_code == 400
                    assert (
                        await client.get(
                            "/api/production/admin/clients/orders",
                            params={"key": "user:3", "limit": 101},
                        )
                    ).status_code == 422
                assert not any(
                    "orders.cart_items" in sql or "admin_inbox_items.message" in sql
                    for sql in statements
                )
                async with AsyncClient(
                    transport=ASGITransport(app), base_url="https://test"
                ) as client:
                    await client.post("/api/production/auth/login", json={"code": cutter})
                    denied = await client.get(
                        "/api/production/admin/clients/orders", params={"key": "user:3"}
                    )
                    assert (
                        denied.status_code == 403 and denied.headers["cache-control"] == "no-store"
                    )
            finally:
                event.remove(db.engine.sync_engine, "before_cursor_execute", capture)

    asyncio.run(scenario())


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
def test_guest_history_groups_match_directory_without_merging_registered_buyers(tmp_path, dialect):
    postgres_url = os.getenv("PRODUCTION_TEST_POSTGRES_URL") if dialect == "postgresql" else None
    if dialect == "postgresql" and not postgres_url:
        pytest.skip("Isolated PostgreSQL CI required")

    async def scenario():
        async with admin_app(tmp_path, postgres_url=postgres_url) as (_app, db, _code, _cutter):
            async with db.session() as session:
                for number, account, email, phone in [
                    (5000, None, "guest@example.test", "+70000000000"),
                    (5001, None, "guest@example.test", "+70000000001"),
                    (5002, 3, "guest@example.test", "+70000000000"),
                    (5003, None, None, "+70000000000"),
                    (5004, None, None, "+70000000000"),
                    (5005, None, None, None),
                ]:
                    session.add(
                        Order(
                            id=number,
                            request_fingerprint_sha256=f"{number:064x}",
                            user_id=account,
                            email=email,
                            email_normalized=email,
                            phone=phone,
                            first_name="Гость",
                            items_subtotal=Decimal("10"),
                            delivery_price=Decimal("0"),
                            total_price=Decimal("10"),
                        )
                    )
                await session.flush()
                for number, order in [(5000, 5000), (5001, 5003), (5002, 5002), (5003, 5005)]:
                    session.add(
                        AdminInboxItem(
                            id=number,
                            kind="support",
                            subject="Обращение",
                            message="Тело",
                            order_id=order,
                        )
                    )
                session.add(
                    AdminInboxItem(
                        id=5004,
                        kind="support",
                        subject="По почте",
                        message="Тело",
                        reporter_email="Guest@Example.test",
                    )
                )
                session.add(
                    AdminInboxItem(
                        id=5005,
                        kind="support",
                        subject="По телефону",
                        message="Тело",
                        reporter_phone="+70000000000",
                    )
                )
                await session.commit()
                service = ProductionClientService()
                for key, orders, tickets in [
                    ("email:guest@example.test", {5000, 5001}, {5000, 5004}),
                    ("phone:+70000000000", {5003, 5004}, {5001, 5005}),
                    ("order:5005", {5005}, {5003}),
                ]:
                    profile = await service.detail(session, key=key)
                    assert profile["orders_count"] == len(orders)
                    assert profile["tickets_count"] == len(tickets)
                    assert profile["account"] is None
                    for kind, expected in [("orders", orders), ("tickets", tickets)]:
                        page = await service.history(
                            session, kind=kind, query=ClientHistoryQuery(key=key)
                        )
                        assert {item.id for item in page.items} == expected
                        assert page.next_cursor is None

    asyncio.run(scenario())
