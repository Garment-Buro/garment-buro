from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import OtpSecurity
from app.modules.orders.models import LegacyOrderClaim, LegacyOrderImport, Order
from app.modules.orders.service import TargetOrderReadService


def test_verified_email_claim_cannot_be_stolen_and_phone_is_not_ownership(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        identity_repository = IdentityRepository()
        orders = TargetOrderReadService(OtpSecurity("p" * 32))
        now = datetime.now(timezone.utc)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await identity_repository.ensure_system_authorization(session)
            for order_id, email, phone in (
                (1, "owner@example.test", "+79990000001"),
                (2, None, "+79990000001"),
                (3, "someone@example.test", None),
            ):
                session.add(
                    Order(
                        id=order_id,
                        email=email,
                        email_normalized=email,
                        phone=phone,
                        items_subtotal=Decimal("100.00"),
                        delivery_price=Decimal("0.00"),
                        total_price=Decimal("100.00"),
                        request_fingerprint_sha256=f"{order_id:064x}",
                        legacy_import=LegacyOrderImport(
                            source_order_id=order_id,
                            source_row_sha256=f"{order_id:064x}",
                            raw_cart_items="[]",
                            legacy_total_price=Decimal("100.00"),
                        ),
                    )
                )
            owner = await identity_repository.create_customer(
                session,
                email="owner@example.test",
                email_normalized="owner@example.test",
            )
            owner.email_verified_at = now
            owner.phone = "+79990000001"
            await session.commit()

        async with database.session() as session:
            owner_orders = await orders.list_owned_orders(session, user=owner)
            await session.commit()
        assert [order.id for order in owner_orders.items] == [1]

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
            second_orders = await orders.list_owned_orders(session, user=second_user)
            await session.commit()
            claim = await session.scalar(select(LegacyOrderClaim))
        assert second_orders.items == []
        assert claim is not None
        assert claim.user_id == owner.id
        assert claim.legacy_order_id == 1
        assert "owner@example.test" not in claim.identifier_digest
        await database.shutdown()

    asyncio.run(scenario())
