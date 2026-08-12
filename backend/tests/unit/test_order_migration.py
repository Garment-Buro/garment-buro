from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.security import ensure_utc
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.migration import (
    LegacyOrderPlanner,
    OrderMigrationService,
    TargetOrderStoreNotEmptyError,
)
from app.modules.orders.models import (
    LegacyOrderImport,
    Order,
    OrderCreationRequest,
    OrderItem,
    OrderMigrationRun,
    OrderStatusHistory,
)

LEGACY_ORDER_SCHEMA = """
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    email TEXT,
    phone TEXT,
    first_name TEXT,
    last_name TEXT,
    patronymic TEXT,
    delivery_city TEXT,
    delivery_method TEXT,
    delivery_address TEXT,
    payment_method TEXT,
    cart_items TEXT,
    total_price REAL,
    status TEXT,
    cdek_uuid TEXT,
    cdek_point_code TEXT,
    delivery_price REAL,
    payment_id TEXT,
    payment_status TEXT,
    created_at TEXT,
    cdek_number TEXT,
    cdek_status TEXT
)
"""


def _item(
    *,
    item_id: str | None = "legacy-line-1",
    price: str = "100.00",
    quantity: int | None = 2,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "product_id": 7,
        "title": "Private product title",
        "price": price,
        "image": "/uploads/private.webp",
        "size": "M",
        "color": "black",
        "customization": {"fit": {"lengthCm": 70, "widthCm": 58}},
    }
    if item_id is not None:
        payload["id"] = item_id
    if quantity is not None:
        payload["quantity"] = quantity
    return payload


def _insert_order(
    connection: sqlite3.Connection,
    *,
    order_id: int,
    cart_items: object,
    total_price: object = 250,
    delivery_price: object = 50,
    email: str | None = "Customer@Secret.TEST",
    status: str | None = "processing",
    payment_status: str | None = "paid",
    payment_id: str | None = "payment-provider-secret",
    cdek_uuid: str | None = "cdek-provider-secret",
) -> None:
    rendered_cart = cart_items if isinstance(cart_items, str) else json.dumps(cart_items)
    connection.execute(
        """
        INSERT INTO orders (
            id, email, phone, first_name, last_name, patronymic,
            delivery_city, delivery_method, delivery_address, payment_method,
            cart_items, total_price, status, cdek_uuid, cdek_point_code,
            delivery_price, payment_id, payment_status, created_at,
            cdek_number, cdek_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            email,
            "+7 900 000-00-00",
            "Private customer",
            "Surname",
            None,
            "Moscow",
            "cdek_pickup",
            "Private address",
            "card",
            rendered_cart,
            total_price,
            status,
            cdek_uuid,
            "MSK-POINT",
            delivery_price,
            payment_id,
            payment_status,
            "2026-08-01T10:00:00",
            "CDEK-NUMBER-SECRET" if cdek_uuid else None,
            "Created" if cdek_uuid else None,
        ),
    )


def _source(path: Path, *, two_orders: bool = False) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(LEGACY_ORDER_SCHEMA)
        _insert_order(connection, order_id=7, cart_items=[_item()])
        if two_orders:
            _insert_order(
                connection,
                order_id=9,
                cart_items=[_item(item_id=None, price="90.00", quantity=None)],
                total_price=80,
                delivery_price=None,
                email="invalid-email-secret",
                status=None,
                payment_status=None,
                payment_id=None,
                cdek_uuid=None,
            )
        connection.commit()


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
    )


def test_order_migration_plan_is_deterministic_reconciled_and_pii_safe(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy.db"
    _source(source, two_orders=True)

    first = LegacyOrderPlanner().build(source)
    second = LegacyOrderPlanner().build(source)

    assert first.valid
    assert first.fingerprint == second.fingerprint
    assert first.source_orders_count == 2
    assert len(first.orders) == 2 and first.items_count == 2
    assert first.synthetic_item_ids_count == 1
    assert first.total_reconciliation_mismatches_count == 1
    assert first.orders[0].items_subtotal == Decimal("200.00")
    assert first.orders[0].items[0].customization == {"fit": {"lengthCm": 70, "widthCm": 58}}
    assert first.orders[1].delivery_price == Decimal("0.00")
    assert first.orders[1].email_normalized is None

    rendered_report = json.dumps(first.report(), ensure_ascii=False)
    for private_value in (
        "Customer@Secret.TEST",
        "+7 900 000-00-00",
        "Private customer",
        "Private address",
        "payment-provider-secret",
        "cdek-provider-secret",
        "Private product title",
    ):
        assert private_value not in rendered_report

    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE orders SET total_price = 251 WHERE id = 7")
        connection.commit()
    assert LegacyOrderPlanner().build(source).fingerprint != first.fingerprint


def test_order_migration_plan_rejects_unknown_state_and_invalid_cart(tmp_path: Path) -> None:
    source = tmp_path / "invalid.db"
    with sqlite3.connect(source) as connection:
        connection.execute(LEGACY_ORDER_SCHEMA)
        _insert_order(
            connection,
            order_id=3,
            cart_items="{broken",
            status="mystery",
        )
        connection.commit()

    plan = LegacyOrderPlanner().build(source)

    assert not plan.valid
    assert plan.source_orders_count == 1
    assert any("invalid cart JSON" in error for error in plan.errors)
    assert any("unsupported status" in error for error in plan.errors)
    rendered = json.dumps(plan.report())
    assert "payment-provider-secret" not in rendered


def test_order_migration_apply_preserves_ids_snapshots_and_provider_references(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        source = tmp_path / "apply-source.db"
        _source(source)
        plan = LegacyOrderPlanner().build(source)
        settings = _settings(tmp_path / "target.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            migration = OrderMigrationService()
            async with database.session() as session:
                result = await migration.apply(session, plan)
                await session.commit()
                assert result.orders == 1 and result.items == 1
                assert result.payment_references == 1
                assert result.delivery_references == 1

            async with database.session() as session:
                replay = await migration.apply(session, plan)
                await session.commit()
                assert replay.fingerprint_sha256 == plan.fingerprint

            async with database.session() as session:
                order = await session.get(Order, 7)
                item = await session.scalar(select(OrderItem))
                history = await session.scalar(select(OrderStatusHistory))
                imported = await session.scalar(select(LegacyOrderImport))
                run = await session.scalar(select(OrderMigrationRun))
                assert order is not None
                assert order.status == "processing" and order.payment_status == "paid"
                assert order.items_subtotal == Decimal("200.00")
                assert order.delivery_price == Decimal("50.00")
                assert order.total_price == Decimal("250.00")
                assert ensure_utc(order.created_at) == datetime(
                    2026, 8, 1, 10, 0, tzinfo=timezone.utc
                )
                assert item is not None and item.product_id_snapshot == 7
                assert item.variant_id_snapshot is None
                assert item.customization_snapshot == {"fit": {"lengthCm": 70, "widthCm": 58}}
                assert history is not None and history.to_status == "processing"
                assert history.reason_code == "legacy.imported"
                assert imported is not None and imported.source_order_id == 7
                assert imported.payment_provider_id == "payment-provider-secret"
                assert imported.delivery_provider_uuid == "cdek-provider-secret"
                assert imported.raw_cart_items == plan.orders[0].raw_cart_items
                assert run is not None and run.fingerprint_sha256 == plan.fingerprint
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(InventoryReservation))
                        or 0
                    )
                    == 0
                )
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(OrderCreationRequest))
                        or 0
                    )
                    == 0
                )

            with sqlite3.connect(source) as connection:
                connection.execute("UPDATE orders SET total_price = 251 WHERE id = 7")
                connection.commit()
            changed_plan = LegacyOrderPlanner().build(source)
            async with database.session() as session:
                with pytest.raises(TargetOrderStoreNotEmptyError, match="must be empty"):
                    await migration.apply(session, changed_plan)

            async with database.session() as session:
                await session.execute(delete(OrderStatusHistory))
                await session.commit()
            async with database.session() as session:
                with pytest.raises(TargetOrderStoreNotEmptyError, match="does not match"):
                    await migration.apply(session, plan)
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_order_migration_cli_requires_reviewed_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "cli.db"
    _source(source)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "migrate_legacy_orders",
            "--sqlite-db",
            str(source),
            "--apply",
            "--expect-fingerprint",
            "f" * 64,
        ],
    )

    from scripts.migrate_legacy_orders import main

    assert main() == 2
    output = capsys.readouterr().out
    assert "Dry-run fingerprint does not match" in output
    assert "payment-provider-secret" not in output
    assert "Customer@Secret.TEST" not in output
