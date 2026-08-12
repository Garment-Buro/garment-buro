from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.orders.models import LegacyOrderImport, Order
from app.modules.orders.security import (
    InvalidOrderGuestAccessTokenError,
    generate_order_guest_access_token,
)
from app.modules.orders.service import (
    OrderGuestAccessService,
    OrderGuestAccessStateError,
)


def _order(*, user_id: int | None = None) -> Order:
    return Order(
        user_id=user_id,
        email="guest@example.test",
        email_normalized="guest@example.test",
        phone="+79000000000",
        first_name="Guest",
        delivery_city="Moscow",
        delivery_method="pickup",
        delivery_address="Showroom",
        payment_method="card",
        items_subtotal=Decimal("100.00"),
        delivery_price=Decimal("0.00"),
        total_price=Decimal("100.00"),
        status="new",
        payment_status="pending",
        version=1,
        request_fingerprint_sha256="f" * 64,
    )


def test_guest_order_access_expires_revokes_and_rejects_invalid_tokens(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'guest.db'}",
            order_guest_access_ttl_days=30,
        )
        database = DatabaseManager(settings)
        await database.startup()
        now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        expiring_token = "a" * 43
        revoked_token = "b" * 43
        service = OrderGuestAccessService(settings)
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                expiring = _order()
                revoked = _order()
                session.add_all([expiring, revoked])
                await session.flush()
                await service.register(
                    session,
                    order=expiring,
                    token=expiring_token,
                    now=now,
                )
                await service.register(
                    session,
                    order=revoked,
                    token=revoked_token,
                    now=now,
                )
                expiring_id = expiring.id
                revoked_id = revoked.id
                await session.commit()

            async with database.session() as session:
                assert (
                    await service.resolve(
                        session,
                        token=expiring_token,
                        now=now + timedelta(days=29),
                    )
                ).id == expiring_id
                assert (
                    await service.resolve(
                        session,
                        token=expiring_token,
                        now=now + timedelta(days=30),
                    )
                    is None
                )

            async with database.session() as session:
                assert await service.revoke(
                    session,
                    order_id=revoked_id,
                    now=now + timedelta(minutes=1),
                )
                await session.commit()
            async with database.session() as session:
                assert not await service.revoke(
                    session,
                    order_id=revoked_id,
                    now=now + timedelta(minutes=2),
                )
                assert await service.resolve(session, token=revoked_token, now=now) is None

            with pytest.raises(InvalidOrderGuestAccessTokenError):
                async with database.session() as session:
                    await service.resolve(session, token="short", now=now)

            async with database.session() as session:
                owned = _order()
                session.add(owned)
                await session.flush()
                owned.user_id = 123
                with pytest.raises(OrderGuestAccessStateError):
                    await service.register(
                        session,
                        order=owned,
                        token="c" * 43,
                        now=now,
                    )

            async with database.session() as session:
                imported = _order()
                session.add(imported)
                await session.flush()
                session.add(
                    LegacyOrderImport(
                        order_id=imported.id,
                        source_order_id=999,
                        source_row_sha256="d" * 64,
                        raw_cart_items="[]",
                        legacy_total_price=Decimal("100.00"),
                        legacy_status="new",
                        legacy_payment_status="pending",
                    )
                )
                await session.flush()
                with pytest.raises(OrderGuestAccessStateError, match="Imported"):
                    await service.register(
                        session,
                        order=imported,
                        token="e" * 43,
                        now=now,
                    )
        finally:
            await database.shutdown()

    generated = generate_order_guest_access_token()
    assert len(generated) == 43
    asyncio.run(scenario())
