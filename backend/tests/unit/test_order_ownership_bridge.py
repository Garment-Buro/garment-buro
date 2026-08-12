from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import OtpSecurity
from app.modules.orders.legacy import LegacyOrderReader
from app.modules.orders.models import LegacyOrderClaim
from app.modules.orders.service import OrderOwnershipBridgeService


def _create_orders_database(path: Path) -> None:
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
            INSERT INTO orders (id, email, phone, cart_items, total_price, created_at)
            VALUES (?, ?, ?, '[]', 100, '2026-08-11 10:00:00')
            """,
            [
                (1, "owner@example.test", "+79990000001"),
                (2, None, "+79990000001"),
                (3, "someone@example.test", None),
            ],
        )


def test_verified_email_claim_cannot_be_stolen_and_phone_is_not_ownership(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        legacy_path = tmp_path / "orders.db"
        _create_orders_database(legacy_path)
        reader = LegacyOrderReader(f"sqlite:///{legacy_path}")
        reader.validate()

        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        identity_repository = IdentityRepository()
        bridge = OrderOwnershipBridgeService(reader, OtpSecurity("p" * 32))
        now = datetime.now(timezone.utc)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await identity_repository.ensure_system_authorization(session)
            owner = await identity_repository.create_customer(
                session,
                email="owner@example.test",
                email_normalized="owner@example.test",
            )
            owner.email_verified_at = now
            owner.phone = "+79990000001"
            await session.commit()

        async with database.session() as session:
            owner_orders = await bridge.list_owned_orders(session, user=owner)
            await session.commit()
        assert [order.id for order in owner_orders] == [1]

        async with database.session() as session:
            persisted_owner = await identity_repository.get_user(
                session,
                owner.id,
                for_update=True,
            )
            assert persisted_owner is not None
            persisted_owner.email = "changed@example.test"
            persisted_owner.email_normalized = "changed@example.test"
            second_user = await identity_repository.create_customer(
                session,
                email="owner@example.test",
                email_normalized="owner@example.test",
            )
            second_user.email_verified_at = now
            await session.commit()

        async with database.session() as session:
            second_orders = await bridge.list_owned_orders(session, user=second_user)
            await session.commit()
            claim = await session.scalar(select(LegacyOrderClaim))
        assert second_orders == []
        assert claim is not None
        assert claim.user_id == owner.id
        assert claim.legacy_order_id == 1
        assert "owner@example.test" not in claim.identifier_digest
        await database.shutdown()

    asyncio.run(scenario())


def test_legacy_order_reader_rejects_incomplete_schema(tmp_path: Path) -> None:
    path = tmp_path / "incomplete.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY)")

    reader = LegacyOrderReader(f"sqlite:///{path}")
    with pytest.raises(ConfigurationError, match="schema is incompatible"):
        reader.validate()
