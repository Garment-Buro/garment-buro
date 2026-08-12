from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import (
    CrmOrderProject,
    CrmProductionUnit,
    CrmProductionUnitStatus,
    CrmProjectEvent,
    CrmProjectStatus,
)
from app.modules.crm.production_models import (
    CrmProductionUnitEvent,
    CrmProductionUnitEventType,
)


class CrmProjectEvidenceConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CrmProductionUnitSnapshot:
    order_item_id: int
    product_id_snapshot: int
    variant_id_snapshot: int | None
    unit_number: int


class CrmProjectRepository:
    async def acquire_from_paid_order(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        source_fulfillment_job_id: int,
        source_payment_attempt_id: int,
        order_version_snapshot: int,
        total_price_snapshot: Decimal,
        currency: str,
        payment_succeeded_at_snapshot: datetime,
        units: tuple[CrmProductionUnitSnapshot, ...],
        now: datetime,
    ) -> CrmOrderProject:
        item_ids = {unit.order_item_id for unit in units}
        values = {
            "order_id": order_id,
            "source_fulfillment_job_id": source_fulfillment_job_id,
            "source_payment_attempt_id": source_payment_attempt_id,
            "status": CrmProjectStatus.QUEUED.value,
            "version": 1,
            "order_version_snapshot": order_version_snapshot,
            "items_count": len(item_ids),
            "units_count": len(units),
            "total_price_snapshot": total_price_snapshot,
            "currency": currency,
            "payment_succeeded_at_snapshot": payment_succeeded_at_snapshot,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(CrmOrderProject).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(CrmOrderProject).values(**values)
        else:
            raise RuntimeError("CRM paid-order intake requires PostgreSQL or SQLite")
        inserted_id = await session.scalar(
            statement.on_conflict_do_nothing().returning(CrmOrderProject.id)
        )
        project = await session.scalar(
            select(CrmOrderProject)
            .where(
                or_(
                    CrmOrderProject.order_id == order_id,
                    CrmOrderProject.source_fulfillment_job_id == source_fulfillment_job_id,
                )
            )
            .with_for_update()
        )
        if project is None:
            raise RuntimeError("CRM order project could not be acquired")
        if project.order_id != order_id or not self._matches_evidence(project, values):
            raise CrmProjectEvidenceConflictError(
                "CRM order project is linked to different immutable evidence"
            )

        if inserted_id is not None:
            created_units = [
                CrmProductionUnit(
                    project_id=project.id,
                    order_item_id=unit.order_item_id,
                    product_id_snapshot=unit.product_id_snapshot,
                    variant_id_snapshot=unit.variant_id_snapshot,
                    unit_number=unit.unit_number,
                    status=CrmProductionUnitStatus.QUEUED.value,
                )
                for unit in units
            ]
            session.add_all(created_units)
            session.add(
                CrmProjectEvent(
                    project_id=project.id,
                    event_key=f"project:{project.id}:version:1",
                    version=1,
                    from_status=None,
                    to_status=CrmProjectStatus.QUEUED.value,
                    reason_code="paid_order_intake",
                    occurred_at=now,
                )
            )
            await session.flush()
            session.add_all(
                CrmProductionUnitEvent(
                    production_unit_id=unit.id,
                    event_key=f"unit:{unit.id}:version:1",
                    version=1,
                    event_type=CrmProductionUnitEventType.INITIALIZED.value,
                    from_status=None,
                    to_status=CrmProductionUnitStatus.QUEUED.value,
                    reason_code="paid_order_intake",
                    occurred_at=now,
                )
                for unit in created_units
            )
            await session.flush()
        await self._verify_units(session, project.id, units)
        return project

    async def get_for_update(
        self,
        session: AsyncSession,
        *,
        project_id: int,
    ) -> CrmOrderProject | None:
        return await session.scalar(
            select(CrmOrderProject).where(CrmOrderProject.id == project_id).with_for_update()
        )

    async def list_units_for_update(
        self,
        session: AsyncSession,
        *,
        project_id: int,
    ) -> list[CrmProductionUnit]:
        return list(
            await session.scalars(
                select(CrmProductionUnit)
                .where(CrmProductionUnit.project_id == project_id)
                .order_by(CrmProductionUnit.id)
                .with_for_update()
            )
        )

    @staticmethod
    def add_status_event(
        session: AsyncSession,
        project: CrmOrderProject,
        *,
        from_status: str,
        reason_code: str,
        actor_user_id: int | None,
        now: datetime,
    ) -> None:
        session.add(
            CrmProjectEvent(
                project_id=project.id,
                event_key=f"project:{project.id}:version:{project.version}",
                version=project.version,
                from_status=from_status,
                to_status=project.status,
                reason_code=reason_code,
                actor_user_id=actor_user_id,
                occurred_at=now,
            )
        )

    @staticmethod
    def _matches_evidence(project: CrmOrderProject, expected: dict[str, object]) -> bool:
        timestamp = project.payment_succeeded_at_snapshot
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        expected_timestamp = expected["payment_succeeded_at_snapshot"]
        assert isinstance(expected_timestamp, datetime)
        if expected_timestamp.tzinfo is None:
            expected_timestamp = expected_timestamp.replace(tzinfo=timezone.utc)
        else:
            expected_timestamp = expected_timestamp.astimezone(timezone.utc)
        return (
            project.source_fulfillment_job_id == expected["source_fulfillment_job_id"]
            and project.source_payment_attempt_id == expected["source_payment_attempt_id"]
            and project.order_version_snapshot == expected["order_version_snapshot"]
            and project.items_count == expected["items_count"]
            and project.units_count == expected["units_count"]
            and project.total_price_snapshot == expected["total_price_snapshot"]
            and project.currency == expected["currency"]
            and timestamp.astimezone(timezone.utc) == expected_timestamp
        )

    @staticmethod
    async def _verify_units(
        session: AsyncSession,
        project_id: int,
        expected: tuple[CrmProductionUnitSnapshot, ...],
    ) -> None:
        actual = tuple(
            (
                unit.order_item_id,
                unit.product_id_snapshot,
                unit.variant_id_snapshot,
                unit.unit_number,
            )
            for unit in await session.scalars(
                select(CrmProductionUnit)
                .where(CrmProductionUnit.project_id == project_id)
                .order_by(CrmProductionUnit.order_item_id, CrmProductionUnit.unit_number)
            )
        )
        expected_rows = tuple(
            sorted(
                (
                    unit.order_item_id,
                    unit.product_id_snapshot,
                    unit.variant_id_snapshot,
                    unit.unit_number,
                )
                for unit in expected
            )
        )
        if actual != expected_rows:
            raise CrmProjectEvidenceConflictError(
                "CRM production units differ from immutable order evidence"
            )
