from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.carts.models import Cart, CartItem
from app.modules.carts.schemas import CartUpdateRequest, LegacyCartUpdateRequest
from app.modules.carts.security import digest_cart_id
from app.modules.carts.service import CartMaintenanceService, CartRevisionConflictError, CartService


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
    )


def _payload(*, title: str, revision: str | None = None) -> CartUpdateRequest:
    return CartUpdateRequest.model_validate(
        {
            "expected_revision": revision,
            "operation_id": uuid4().hex,
            "items": [
                {
                    "id": "1_M_black",
                    "product_id": 1,
                    "title": title,
                    "price": 1200.50,
                    "image": "/uploads/item.webp",
                    "size": "M",
                    "color": "black",
                    "quantity": 2,
                    "customization": {
                        "fit": {"lengthCm": 70, "widthCm": 58},
                    },
                }
            ],
        }
    )


def test_cart_service_persists_digest_and_rejects_stale_overwrite(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "cart.db")
        database = DatabaseManager(settings)
        await database.startup()
        now = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            service = CartService(settings)
            async with database.session() as session:
                updated = await service.upsert_snapshot(
                    session,
                    cart_id="guest-contract",
                    payload=_payload(title="Newest"),
                    now=now,
                )
                await session.commit()
                assert updated.updated_at_ms == int(now.timestamp() * 1000)
                assert len(updated.items) == 1

            async with database.session() as session:
                with pytest.raises(CartRevisionConflictError):
                    await service.upsert_snapshot(
                        session,
                        cart_id="guest-contract",
                        payload=_payload(title="Stale"),
                        now=now + timedelta(seconds=1),
                    )
                await session.rollback()

            async with database.session() as session:
                snapshot = await service.get_snapshot(
                    session,
                    cart_id="guest-contract",
                    now=now + timedelta(seconds=2),
                )
                assert snapshot.items[0].title == "Newest"
                assert snapshot.items[0].customization == {"fit": {"lengthCm": 70, "widthCm": 58}}
                stored = await session.scalar(select(Cart))
                assert stored is not None
                assert stored.token_digest_sha256 == digest_cart_id("guest-contract")
                assert "guest-contract" not in repr(stored.__dict__)

        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cart_service_treats_expired_cart_as_empty_and_can_reactivate(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "expired-cart.db")
        database = DatabaseManager(settings)
        await database.startup()
        now = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            service = CartService(settings)
            async with database.session() as session:
                await service.upsert_snapshot(
                    session,
                    cart_id="expired-cart",
                    payload=_payload(title="Before"),
                    now=now,
                )
                cart = await session.scalar(select(Cart))
                assert cart is not None
                cart.expires_at = now - timedelta(seconds=1)
                await session.commit()

            async with database.session() as session:
                empty = await service.get_snapshot(
                    session,
                    cart_id="expired-cart",
                    now=now,
                )
                assert empty.items == []
                assert empty.updated_at_ms == 0

            async with database.session() as session:
                reactivated = await service.upsert_snapshot(
                    session,
                    cart_id="expired-cart",
                    payload=_payload(title="After"),
                    now=now,
                )
                await session.commit()
                assert len(reactivated.items) == 1
            async with database.session() as session:
                cart = await session.scalar(select(Cart))
                assert cart is not None and cart.revision == reactivated.revision

            async with database.session() as session:
                cart = await session.scalar(select(Cart))
                assert cart is not None
                cart.expires_at = now - timedelta(seconds=1)
                await session.commit()
            async with database.session() as session:
                assert (
                    await CartMaintenanceService().purge_expired(
                        session,
                        now=now,
                        batch_size=10,
                    )
                    == 1
                )
                await session.commit()
            async with database.session() as session:
                assert await session.scalar(select(Cart)) is None
                assert await session.scalar(select(CartItem)) is None
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cart_service_recovers_from_an_imported_future_timestamp(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "future-import.db")
        database = DatabaseManager(settings)
        await database.startup()
        now = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            service = CartService(settings)
            async with database.session() as session:
                imported = await service.import_legacy_snapshot(
                    session,
                    cart_id="future-import",
                    payload=LegacyCartUpdateRequest(
                        items=_payload(title="Imported").items,
                        updated_at_ms=int((now + timedelta(days=30)).timestamp() * 1000),
                    ),
                    remaining_ttl_seconds=60,
                    now=now,
                )
                await session.commit()
            async with database.session() as session:
                recovered = await service.upsert_snapshot(
                    session,
                    cart_id="future-import",
                    payload=_payload(
                        title="Current",
                        revision=imported.revision,
                    ),
                    now=now + timedelta(seconds=1),
                )
                await session.commit()
                assert len(recovered.items) == 1
            async with database.session() as session:
                snapshot = await service.get_snapshot(
                    session,
                    cart_id="future-import",
                    now=now + timedelta(seconds=2),
                )
                assert snapshot.items[0].title == "Current"
        finally:
            await database.shutdown()

    asyncio.run(scenario())
