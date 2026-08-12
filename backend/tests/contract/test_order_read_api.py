from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.base import Base
from app.db.session import DatabaseManager
from app.factory import create_app
from app.modules.catalog.models import Product
from app.modules.identity.models import IdentityMigrationRun
from app.modules.identity.repository import IdentityRepository
from app.modules.notifications.crypto import (
    EncryptedNotificationPayload,
    NotificationPayloadCodec,
)
from app.modules.orders.migration import LegacyOrderPlanner, OrderMigrationService
from app.modules.orders.schemas import OrderCreationCommand
from app.modules.orders.security import digest_order_guest_access_token
from app.modules.orders.service import OrderCreationService

IDENTITY_FINGERPRINT = "e" * 64
JWT_SECRET = "j" * 32
OTP_PEPPER = "p" * 32
NOTIFICATION_KEY = base64.urlsafe_b64encode(b"n" * 32).decode("ascii").rstrip("=")
GUEST_ACCESS_TOKEN = "g" * 43


def _create_legacy_orders(path: Path) -> dict[int, str]:
    carts = {
        10: json.dumps(
            [
                {
                    "id": "owned-line",
                    "product_id": 1,
                    "title": "Owned item",
                    "price": 100,
                    "image": "/uploads/owned.webp",
                    "size": "M",
                    "color": "black",
                    "quantity": 1,
                    "customization": {"fit": {"lengthCm": 70, "widthCm": 58}},
                }
            ]
        ),
        11: json.dumps(
            [
                {
                    "id": "other-line",
                    "product_id": 2,
                    "title": "Other item",
                    "price": 200,
                    "image": "",
                    "size": "L",
                    "color": "white",
                    "quantity": 1,
                }
            ]
        ),
    }
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY, email TEXT, phone TEXT, first_name TEXT,
                last_name TEXT, patronymic TEXT, delivery_city TEXT,
                delivery_method TEXT, delivery_address TEXT, payment_method TEXT,
                cart_items TEXT, total_price REAL, status TEXT, cdek_uuid TEXT,
                cdek_point_code TEXT, delivery_price REAL, payment_id TEXT,
                payment_status TEXT, created_at TEXT, cdek_number TEXT,
                cdek_status TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO orders (
                id, email, phone, first_name, delivery_city, delivery_method,
                delivery_address, payment_method, cart_items, total_price,
                status, delivery_price, payment_id, payment_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    10,
                    "Customer@Example.TEST",
                    "+79990000001",
                    "Customer",
                    "Moscow",
                    "cdek_pickup",
                    "Pickup point",
                    "card",
                    carts[10],
                    150,
                    "new",
                    50,
                    "payment-10",
                    "pending",
                    "2026-08-11T08:00:00",
                ),
                (
                    11,
                    "other@example.test",
                    "+79990000002",
                    "Other",
                    "Moscow",
                    "pickup",
                    "Showroom",
                    "cash",
                    carts[11],
                    200,
                    "completed",
                    0,
                    None,
                    "paid",
                    "2026-08-11T09:00:00",
                ),
            ],
        )
        connection.commit()
    return carts


def _settings(tmp_path: Path, *, order_fingerprint: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        legacy_database_url=f"sqlite:///{tmp_path / 'missing-legacy.db'}",
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'target.db'}",
        identity_api_enabled=True,
        identity_migration_fingerprint=IDENTITY_FINGERPRINT,
        order_reads_enabled=True,
        order_migration_fingerprint=order_fingerprint,
        jwt_secret=JWT_SECRET,
        identity_otp_pepper=OTP_PEPPER,
        notification_encryption_key=NOTIFICATION_KEY,
    )


def _seed_target(settings: Settings, source_path: Path) -> int:
    async def seed() -> int:
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                await IdentityRepository().ensure_system_authorization(session)
                session.add(
                    IdentityMigrationRun(
                        fingerprint_sha256=IDENTITY_FINGERPRINT,
                        users_count=0,
                    )
                )
                result = await OrderMigrationService().apply(
                    session,
                    LegacyOrderPlanner().build(source_path),
                )
                assert result.orders == 2
                product = Product(
                    title="Guest target product",
                    price=Decimal("300.00"),
                    is_active=True,
                    stock_quantity=5,
                    sizes=["M"],
                    colors=["black"],
                )
                session.add(product)
                await session.flush()
                guest_order = await OrderCreationService(settings).create(
                    session,
                    idempotency_key="guest_checkout_attempt_0001",
                    guest_access_token=GUEST_ACCESS_TOKEN,
                    command=OrderCreationCommand.model_validate(
                        {
                            "email": "guest@example.test",
                            "phone": "+79000000003",
                            "first_name": "Guest",
                            "delivery_city": "Moscow",
                            "delivery_method": "pickup",
                            "delivery_address": "Showroom",
                            "payment_method": "card",
                            "items": [
                                {
                                    "id": "guest-target-line",
                                    "product_id": product.id,
                                    "title": "Ignored",
                                    "price": "1.00",
                                    "size": "M",
                                    "color": "black",
                                    "quantity": 1,
                                }
                            ],
                            "claimed_total_price": "300.00",
                            "delivery_price": "0.00",
                        }
                    ),
                )
                await session.commit()
                return guest_order.order_id
        finally:
            await database.shutdown()

    return asyncio.run(seed())


def _latest_otp(target_path: Path) -> str:
    with sqlite3.connect(target_path) as connection:
        row = connection.execute(
            """
            SELECT payload_ciphertext, payload_nonce, payload_tag,
                   encryption_key_version
            FROM notification_outbox
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    assert row is not None
    payload = NotificationPayloadCodec.from_base64_key(NOTIFICATION_KEY).decrypt(
        EncryptedNotificationPayload(
            ciphertext=row[0],
            nonce=row[1],
            tag=row[2],
            key_version=row[3],
        )
    )
    return str(payload["code"])


def _login(client: TestClient, target_path: Path, email: str) -> tuple[str, int]:
    assert client.post("/api/auth/email/request", json={"email": email}).status_code == 200
    verified = client.post(
        "/api/auth/email/verify",
        json={"email": email, "code": _latest_otp(target_path)},
    )
    assert verified.status_code == 200
    return str(verified.json()["token"]), int(verified.json()["user"]["id"])


def test_guarded_order_reads_require_owner_or_staff_permission(tmp_path: Path) -> None:
    source_path = tmp_path / "legacy.db"
    target_path = tmp_path / "target.db"
    carts = _create_legacy_orders(source_path)
    plan = LegacyOrderPlanner().build(source_path)
    settings = _settings(tmp_path, order_fingerprint=plan.fingerprint)
    guest_order_id = _seed_target(settings, source_path)

    legacy = FastAPI()

    @legacy.post("/api/orders")
    async def legacy_create_order() -> dict[str, str]:
        return {"source": "legacy-write"}

    @legacy.get("/api/orders/{order_id}")
    async def legacy_public_order(order_id: int) -> dict[str, int | str]:
        return {"source": "legacy-public-read", "id": order_id}

    application = create_app(
        settings=settings,
        database=DatabaseManager(settings),
        legacy_app=legacy,
    )
    with TestClient(application) as client:
        assert client.get("/api/orders/10").status_code == 401
        assert client.post("/api/orders").json() == {"source": "legacy-write"}
        missing_guest_access = client.get("/api/order-access")
        assert missing_guest_access.status_code == 404
        assert missing_guest_access.headers["cache-control"] == "no-store"
        invalid_guest_access = client.get(
            "/api/order-access",
            headers={"X-Order-Access-Token": "invalid"},
        )
        assert invalid_guest_access.status_code == 404
        assert invalid_guest_access.headers["cache-control"] == "no-store"
        guest_detail = client.get(
            "/api/order-access",
            headers={"X-Order-Access-Token": GUEST_ACCESS_TOKEN},
        )
        assert guest_detail.status_code == 200
        assert guest_detail.headers["cache-control"] == "no-store"
        assert guest_detail.json()["id"] == guest_order_id
        assert json.loads(guest_detail.json()["cart_items"])[0]["title"] == ("Guest target product")

        customer_token, customer_id = _login(
            client,
            target_path,
            "Customer@Example.TEST",
        )
        customer_headers = {"Authorization": f"Bearer {customer_token}"}
        owned = client.get("/api/auth/orders", headers=customer_headers)
        assert owned.status_code == 200
        assert [order["id"] for order in owned.json()] == [10]
        assert owned.json()[0]["cart_items"] == carts[10]
        assert json.loads(owned.json()[0]["cart_items"])[0]["customization"] == {
            "fit": {"lengthCm": 70, "widthCm": 58}
        }

        own_detail = client.get("/api/orders/10", headers=customer_headers)
        assert own_detail.status_code == 200
        assert own_detail.json()["payment_id"] == "payment-10"
        assert client.get("/api/orders/11", headers=customer_headers).status_code == 404
        assert client.get("/api/orders", headers=customer_headers).status_code == 403

        with sqlite3.connect(target_path) as connection:
            connection.execute(
                "UPDATE users SET email = ?, email_normalized = ? WHERE id = ?",
                ("changed@example.test", "changed@example.test", customer_id),
            )
            connection.commit()
        retained = client.get("/api/auth/orders", headers=customer_headers)
        assert [order["id"] for order in retained.json()] == [10]

        manager_token, manager_id = _login(client, target_path, "manager@example.test")
        with sqlite3.connect(target_path) as connection:
            connection.execute(
                """
                INSERT INTO user_roles (user_id, role_id, assigned_by_user_id, created_at)
                SELECT ?, id, NULL, CURRENT_TIMESTAMP FROM roles WHERE name = 'manager'
                """,
                (manager_id,),
            )
            connection.commit()
        manager_headers = {"Authorization": f"Bearer {manager_token}"}
        listed = client.get("/api/orders?limit=1&offset=0", headers=manager_headers)
        assert listed.status_code == 200
        assert [order["id"] for order in listed.json()] == [guest_order_id]
        assert client.get("/api/orders/10", headers=manager_headers).status_code == 200

    with sqlite3.connect(target_path) as connection:
        claim = connection.execute(
            """
            SELECT user_id, legacy_order_id, identifier_digest
            FROM legacy_order_claims
            WHERE user_id = ?
            """,
            (customer_id,),
        ).fetchone()
        guest_access = connection.execute(
            "SELECT token_digest_sha256 FROM order_guest_access WHERE order_id = ?",
            (guest_order_id,),
        ).fetchone()
    assert claim is not None and claim[1] == 10
    assert "customer@example.test" not in "|".join(str(value) for value in claim)
    assert guest_access == (digest_order_guest_access_token(GUEST_ACCESS_TOKEN),)
    assert GUEST_ACCESS_TOKEN not in str(guest_access)


def test_order_read_cutover_refuses_wrong_fingerprint_and_tampered_counts(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "legacy.db"
    _create_legacy_orders(source_path)
    plan = LegacyOrderPlanner().build(source_path)
    settings = _settings(tmp_path, order_fingerprint=plan.fingerprint)
    _seed_target(settings, source_path)

    wrong_settings = _settings(tmp_path, order_fingerprint="f" * 64)
    with pytest.raises(ConfigurationError, match="not present"):
        with TestClient(
            create_app(
                settings=wrong_settings,
                database=DatabaseManager(wrong_settings),
            )
        ):
            pass

    with sqlite3.connect(tmp_path / "target.db") as connection:
        connection.execute("DELETE FROM legacy_order_imports WHERE source_order_id = 11")
        connection.commit()
    with pytest.raises(ConfigurationError, match="does not match"):
        with TestClient(create_app(settings=settings, database=DatabaseManager(settings))):
            pass

    payment_tamper_dir = tmp_path / "payment-tamper"
    payment_tamper_dir.mkdir()
    payment_source = payment_tamper_dir / "legacy.db"
    _create_legacy_orders(payment_source)
    payment_plan = LegacyOrderPlanner().build(payment_source)
    payment_settings = _settings(
        payment_tamper_dir,
        order_fingerprint=payment_plan.fingerprint,
    )
    _seed_target(payment_settings, payment_source)
    with sqlite3.connect(payment_tamper_dir / "target.db") as connection:
        connection.execute(
            """
            INSERT INTO payments (
                order_id, provider, status, amount, currency, succeeded_at,
                created_at, updated_at
            ) VALUES (10, 'yookassa', 'pending', 500, 'RUB', NULL,
                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.commit()
    with pytest.raises(ConfigurationError, match="does not match"):
        with TestClient(
            create_app(
                settings=payment_settings,
                database=DatabaseManager(payment_settings),
            )
        ):
            pass
