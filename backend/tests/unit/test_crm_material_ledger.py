from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.crm.material_models import (
    CrmMaterialBalance,
    CrmMaterialMovement,
    CrmMaterialReservation,
)
from app.modules.crm.material_service import CrmMaterialConflictError, CrmMaterialService
from app.modules.crm.models import CrmProductionUnit
from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.crm.reference_models import CrmFabric

NOW = datetime(2026, 8, 12, 23, 0, tzinfo=timezone.utc)


def test_material_ledger_is_idempotent_and_balances_reservations(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'ledger.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                session.add(
                    CrmFabric(
                        code="FAB",
                        name="Fabric",
                        color_name="Black",
                        width_cm=Decimal("150"),
                        currency="RUB",
                        is_active=True,
                        version=1,
                    )
                )
                session.add(
                    CrmProductionUnit(
                        project_id=1,
                        order_item_id=1,
                        product_id_snapshot=1,
                        unit_number=1,
                        status="queued",
                        version=1,
                    )
                )
                session.add(
                    CrmProductionPlanRevision(
                        production_unit_id=1,
                        revision_number=1,
                        garment_model_id=1,
                        garment_size_id=None,
                        tech_card_revision_id=1,
                        status="active",
                        evidence_sha256="a" * 64,
                        planned_at=NOW,
                    )
                )
                await session.commit()
            service = CrmMaterialService()
            async with database.session() as session:
                receipt = await service.receive(
                    session,
                    fabric_id=1,
                    quantity_meters=Decimal("10"),
                    idempotency_key="receipt-1",
                    reason_code="supplier_receipt",
                    actor_user_id=None,
                    now=NOW,
                )
                await session.commit()
                assert receipt.balance_on_hand_after == Decimal("10.000")
            async with database.session() as session:
                replay = await service.receive(
                    session,
                    fabric_id=1,
                    quantity_meters=Decimal("10"),
                    idempotency_key="receipt-1",
                    reason_code="supplier_receipt",
                    actor_user_id=None,
                    now=NOW,
                )
                assert replay.id == 1
                with pytest.raises(CrmMaterialConflictError, match="reused"):
                    await service.receive(
                        session,
                        fabric_id=1,
                        quantity_meters=Decimal("11"),
                        idempotency_key="receipt-1",
                        reason_code="supplier_receipt",
                        actor_user_id=None,
                        now=NOW,
                    )
            async with database.session() as session:
                reservation, _ = await service.reserve(
                    session,
                    plan_revision_id=1,
                    fabric_id=1,
                    quantity_meters=Decimal("6"),
                    idempotency_key="reserve-1",
                    actor_user_id=None,
                    now=NOW,
                )
                await session.commit()
                reservation_id = reservation.id
            async with database.session() as session:
                with pytest.raises(CrmMaterialConflictError, match="reserved fabric"):
                    await service.adjust(
                        session,
                        fabric_id=1,
                        quantity_meters=Decimal("5"),
                        direction="out",
                        idempotency_key="adjust-1",
                        reason_code="inventory_adjustment",
                        actor_user_id=None,
                        now=NOW,
                    )
                await service.consume(
                    session,
                    reservation_id=reservation_id,
                    quantity_meters=Decimal("4"),
                    idempotency_key="consume-1",
                    reason_code="production_consumed",
                    actor_user_id=None,
                    now=NOW,
                )
                await service.release(
                    session,
                    reservation_id=reservation_id,
                    quantity_meters=Decimal("2"),
                    idempotency_key="release-1",
                    reason_code="production_released",
                    actor_user_id=None,
                    now=NOW,
                )
                await session.commit()
            async with database.session() as session:
                balance = await session.get(CrmMaterialBalance, 1)
                reservation = await session.get(CrmMaterialReservation, reservation_id)
                movements = list(
                    await session.scalars(
                        select(CrmMaterialMovement).order_by(CrmMaterialMovement.id)
                    )
                )
                assert balance is not None and reservation is not None
                assert (balance.on_hand_meters, balance.reserved_meters) == (
                    Decimal("6.000"),
                    Decimal("0.000"),
                )
                assert (
                    reservation.consumed_meters,
                    reservation.released_meters,
                    reservation.status,
                ) == (Decimal("4.000"), Decimal("2.000"), "closed")
                assert [movement.movement_type for movement in movements] == [
                    "receipt",
                    "reserve",
                    "consume",
                    "release",
                ]
        finally:
            await database.shutdown()

    asyncio.run(scenario())
