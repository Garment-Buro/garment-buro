from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import CrmProductionUnit, CrmProductionUnitStatus
from app.modules.crm.production_models import (
    CrmProductionPlanRevision,
    CrmProductionPlanStatus,
    CrmProductionUnitEvent,
    CrmProductionUnitEventType,
)
from app.modules.crm.production_repository import CrmProductionRepository
from app.modules.crm.service import CRM_REASON_CODE_PATTERN
from app.modules.identity.security import ensure_utc

CRM_UNIT_TRANSITIONS: dict[str, frozenset[str]] = {
    CrmProductionUnitStatus.QUEUED.value: frozenset(
        {CrmProductionUnitStatus.IN_PROGRESS.value, CrmProductionUnitStatus.CANCELLED.value}
    ),
    CrmProductionUnitStatus.IN_PROGRESS.value: frozenset(
        {
            CrmProductionUnitStatus.QUALITY_CONTROL.value,
            CrmProductionUnitStatus.CANCELLED.value,
        }
    ),
    CrmProductionUnitStatus.QUALITY_CONTROL.value: frozenset(
        {
            CrmProductionUnitStatus.IN_PROGRESS.value,
            CrmProductionUnitStatus.COMPLETED.value,
            CrmProductionUnitStatus.CANCELLED.value,
        }
    ),
    CrmProductionUnitStatus.COMPLETED.value: frozenset(),
    CrmProductionUnitStatus.CANCELLED.value: frozenset(),
}


class CrmProductionNotFoundError(LookupError):
    pass


class CrmProductionConflictError(ValueError):
    pass


class CrmProductionVersionConflictError(RuntimeError):
    pass


class CrmProductionService:
    def __init__(self, repository: CrmProductionRepository | None = None) -> None:
        self.repository = repository or CrmProductionRepository()

    async def plan_unit(
        self,
        session: AsyncSession,
        *,
        production_unit_id: int,
        expected_version: int,
        garment_size_id: int | None,
        tech_card_revision_id: int,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmProductionPlanRevision:
        unit = await self._require_unit(session, production_unit_id)
        if unit.status != CrmProductionUnitStatus.QUEUED.value:
            raise CrmProductionConflictError("Only a queued production unit can be planned")
        link = await self.repository.get_catalog_model_link(
            session,
            catalog_product_id=unit.product_id_snapshot,
        )
        if link is None:
            raise CrmProductionConflictError(
                "Production unit product has no CRM garment-model link"
            )
        order_item = await self.repository.get_order_item(
            session,
            order_item_id=unit.order_item_id,
        )
        if order_item is None:
            raise CrmProductionConflictError("Production unit order evidence is missing")
        sizes = await self.repository.list_active_sizes(
            session,
            garment_model_id=link.garment_model_id,
        )
        size = next((candidate for candidate in sizes if candidate.id == garment_size_id), None)
        if sizes and size is None:
            raise CrmProductionConflictError("An active garment size is required")
        if not sizes and garment_size_id is not None:
            raise CrmProductionConflictError("Garment model has no active sizes")
        if size is not None and order_item.size_snapshot.strip().upper() != size.code:
            raise CrmProductionConflictError("Garment size differs from immutable order evidence")
        revision_evidence = await self.repository.get_published_revision(
            session,
            tech_card_revision_id=tech_card_revision_id,
        )
        if revision_evidence is None:
            raise CrmProductionConflictError("Published tech-card revision is required")
        revision, card = revision_evidence
        if card.garment_model_id != link.garment_model_id:
            raise CrmProductionConflictError("Tech card belongs to another garment model")

        evidence_sha256 = self._evidence_digest(
            production_unit_id=unit.id,
            order_item_id=unit.order_item_id,
            product_id=unit.product_id_snapshot,
            variant_id=unit.variant_id_snapshot,
            garment_model_id=link.garment_model_id,
            garment_size_id=size.id if size is not None else None,
            tech_card_revision_id=revision.id,
        )
        plans = await self.repository.list_plan_revisions_for_update(
            session,
            production_unit_id=unit.id,
        )
        active = next(
            (plan for plan in plans if plan.status == CrmProductionPlanStatus.ACTIVE.value),
            None,
        )
        if active is not None and active.evidence_sha256 == evidence_sha256:
            return active
        self._require_version(unit.version, expected_version)
        if active is not None:
            if await self.repository.has_active_material_reservations(
                session,
                plan_revision_id=active.id,
            ):
                raise CrmProductionConflictError(
                    "Release active material reservations before replanning"
                )
            active.status = CrmProductionPlanStatus.SUPERSEDED.value
            await session.flush()

        occurred_at = ensure_utc(now or datetime.now(timezone.utc))
        plan = CrmProductionPlanRevision(
            production_unit_id=unit.id,
            revision_number=len(plans) + 1,
            based_on_plan_revision_id=active.id if active is not None else None,
            garment_model_id=link.garment_model_id,
            garment_size_id=size.id if size is not None else None,
            tech_card_revision_id=revision.id,
            status=CrmProductionPlanStatus.ACTIVE.value,
            evidence_sha256=evidence_sha256,
            planned_by_user_id=actor_user_id,
            planned_at=occurred_at,
        )
        session.add(plan)
        await session.flush()
        unit.version += 1
        self._add_event(
            session,
            unit=unit,
            event_type=CrmProductionUnitEventType.PLANNED,
            from_status=unit.status,
            plan_revision_id=plan.id,
            reason_code="production_planned",
            actor_user_id=actor_user_id,
            occurred_at=occurred_at,
        )
        await session.flush()
        return plan

    async def transition_unit(
        self,
        session: AsyncSession,
        *,
        production_unit_id: int,
        expected_version: int,
        to_status: CrmProductionUnitStatus,
        reason_code: str,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmProductionUnit:
        if not CRM_REASON_CODE_PATTERN.fullmatch(reason_code):
            raise CrmProductionConflictError("Production reason code has an invalid format")
        unit = await self._require_unit(session, production_unit_id)
        self._require_version(unit.version, expected_version)
        if to_status.value not in CRM_UNIT_TRANSITIONS[unit.status]:
            raise CrmProductionConflictError(
                f"Production unit cannot transition from {unit.status} to {to_status.value}"
            )
        plans = await self.repository.list_plan_revisions_for_update(
            session,
            production_unit_id=unit.id,
        )
        active = next(
            (plan for plan in plans if plan.status == CrmProductionPlanStatus.ACTIVE.value),
            None,
        )
        if to_status == CrmProductionUnitStatus.IN_PROGRESS and active is None:
            raise CrmProductionConflictError("Production unit must have an active plan")
        if (
            to_status
            in {
                CrmProductionUnitStatus.COMPLETED,
                CrmProductionUnitStatus.CANCELLED,
            }
            and active is not None
            and await self.repository.has_active_material_reservations(
                session,
                plan_revision_id=active.id,
            )
        ):
            raise CrmProductionConflictError(
                "Consume or release active material reservations before closing the unit"
            )

        occurred_at = ensure_utc(now or datetime.now(timezone.utc))
        previous = unit.status
        unit.status = to_status.value
        unit.version += 1
        if to_status == CrmProductionUnitStatus.IN_PROGRESS and unit.started_at is None:
            unit.started_at = occurred_at
        if to_status in {
            CrmProductionUnitStatus.COMPLETED,
            CrmProductionUnitStatus.CANCELLED,
        }:
            unit.closed_at = occurred_at
        self._add_event(
            session,
            unit=unit,
            event_type=CrmProductionUnitEventType.STATUS_CHANGED,
            from_status=previous,
            plan_revision_id=None,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            occurred_at=occurred_at,
        )
        await session.flush()
        return unit

    async def _require_unit(
        self,
        session: AsyncSession,
        production_unit_id: int,
    ) -> CrmProductionUnit:
        unit = await self.repository.get_unit_for_update(
            session,
            production_unit_id=production_unit_id,
        )
        if unit is None:
            raise CrmProductionNotFoundError("CRM production unit was not found")
        return unit

    @staticmethod
    def _require_version(actual: int, expected: int) -> None:
        if expected <= 0 or actual != expected:
            raise CrmProductionVersionConflictError("CRM production unit version has changed")

    @staticmethod
    def _add_event(
        session: AsyncSession,
        *,
        unit: CrmProductionUnit,
        event_type: CrmProductionUnitEventType,
        from_status: str,
        plan_revision_id: int | None,
        reason_code: str,
        actor_user_id: int | None,
        occurred_at: datetime,
    ) -> None:
        session.add(
            CrmProductionUnitEvent(
                production_unit_id=unit.id,
                event_key=f"unit:{unit.id}:version:{unit.version}",
                version=unit.version,
                event_type=event_type.value,
                from_status=from_status,
                to_status=unit.status,
                production_plan_revision_id=plan_revision_id,
                reason_code=reason_code,
                actor_user_id=actor_user_id,
                occurred_at=occurred_at,
            )
        )

    @staticmethod
    def _evidence_digest(**values: int | None) -> str:
        canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
