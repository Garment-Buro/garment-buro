from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.material_models import (
    CrmMaterialBalance,
    CrmMaterialMovement,
    CrmMaterialReservation,
)
from app.modules.crm.models import CrmProductionUnit, CrmProductionUnitStatus
from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.crm.reference_models import CrmFabric


class CrmMaterialRepository:
    async def get_active_fabric(
        self,
        session: AsyncSession,
        *,
        fabric_id: int,
    ) -> CrmFabric | None:
        return await session.scalar(
            select(CrmFabric)
            .where(CrmFabric.id == fabric_id, CrmFabric.is_active.is_(True))
            .with_for_update()
        )

    async def acquire_balance(
        self,
        session: AsyncSession,
        *,
        fabric_id: int,
        now: datetime,
    ) -> CrmMaterialBalance:
        values = {
            "fabric_id": fabric_id,
            "on_hand_meters": 0,
            "reserved_meters": 0,
            "version": 1,
            "updated_at": now,
        }
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgresql_insert(CrmMaterialBalance).values(**values)
        elif dialect == "sqlite":
            statement = sqlite_insert(CrmMaterialBalance).values(**values)
        else:
            raise RuntimeError("CRM material ledger requires PostgreSQL or SQLite")
        await session.execute(statement.on_conflict_do_nothing(index_elements=["fabric_id"]))
        balance = await session.scalar(
            select(CrmMaterialBalance)
            .where(CrmMaterialBalance.fabric_id == fabric_id)
            .with_for_update()
        )
        if balance is None:
            raise RuntimeError("CRM material balance could not be acquired")
        return balance

    async def get_movement(
        self,
        session: AsyncSession,
        *,
        fabric_id: int,
        key_sha256: str,
    ) -> CrmMaterialMovement | None:
        return await session.scalar(
            select(CrmMaterialMovement).where(
                CrmMaterialMovement.fabric_id == fabric_id,
                CrmMaterialMovement.idempotency_key_sha256 == key_sha256,
            )
        )

    async def get_active_plan(
        self,
        session: AsyncSession,
        *,
        plan_revision_id: int,
    ) -> CrmProductionPlanRevision | None:
        return await session.scalar(
            select(CrmProductionPlanRevision)
            .where(
                CrmProductionPlanRevision.id == plan_revision_id,
                CrmProductionPlanRevision.status == "active",
            )
            .with_for_update()
        )

    async def get_reservable_plan(
        self,
        session: AsyncSession,
        *,
        plan_revision_id: int,
    ) -> CrmProductionPlanRevision | None:
        return await session.scalar(
            select(CrmProductionPlanRevision)
            .join(
                CrmProductionUnit,
                CrmProductionUnit.id == CrmProductionPlanRevision.production_unit_id,
            )
            .where(
                CrmProductionPlanRevision.id == plan_revision_id,
                CrmProductionPlanRevision.status == "active",
                CrmProductionUnit.status.in_(
                    (
                        CrmProductionUnitStatus.QUEUED.value,
                        CrmProductionUnitStatus.IN_PROGRESS.value,
                    )
                ),
            )
            .with_for_update()
        )

    async def list_active_reservations_for_units(
        self,
        session: AsyncSession,
        *,
        production_unit_ids: tuple[int, ...],
    ) -> list[CrmMaterialReservation]:
        if not production_unit_ids:
            return []
        return list(
            await session.scalars(
                select(CrmMaterialReservation)
                .join(
                    CrmProductionPlanRevision,
                    CrmProductionPlanRevision.id
                    == CrmMaterialReservation.production_plan_revision_id,
                )
                .where(
                    CrmProductionPlanRevision.production_unit_id.in_(production_unit_ids),
                    CrmMaterialReservation.status == "active",
                )
                .order_by(CrmMaterialReservation.id)
                .with_for_update()
            )
        )

    async def get_reservation_for_update(
        self,
        session: AsyncSession,
        *,
        reservation_id: int,
    ) -> CrmMaterialReservation | None:
        return await session.scalar(
            select(CrmMaterialReservation)
            .where(CrmMaterialReservation.id == reservation_id)
            .with_for_update()
        )

    async def get_plan_fabric_reservation(
        self,
        session: AsyncSession,
        *,
        plan_revision_id: int,
        fabric_id: int,
    ) -> CrmMaterialReservation | None:
        return await session.scalar(
            select(CrmMaterialReservation).where(
                CrmMaterialReservation.production_plan_revision_id == plan_revision_id,
                CrmMaterialReservation.fabric_id == fabric_id,
            )
        )
