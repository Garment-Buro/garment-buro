from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.material_repository import CrmMaterialRepository
from app.modules.crm.models import (
    CrmOrderProject,
    CrmProductionUnit,
    CrmProductionUnitStatus,
    CrmProjectStatus,
)
from app.modules.crm.repository import CrmProjectRepository
from app.modules.identity.security import ensure_utc

CRM_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
CRM_PROJECT_TRANSITIONS: dict[str, frozenset[str]] = {
    CrmProjectStatus.QUEUED.value: frozenset(
        {
            CrmProjectStatus.IN_PROGRESS.value,
            CrmProjectStatus.ON_HOLD.value,
            CrmProjectStatus.CANCELLED.value,
        }
    ),
    CrmProjectStatus.IN_PROGRESS.value: frozenset(
        {
            CrmProjectStatus.ON_HOLD.value,
            CrmProjectStatus.COMPLETED.value,
            CrmProjectStatus.CANCELLED.value,
        }
    ),
    CrmProjectStatus.ON_HOLD.value: frozenset(
        {
            CrmProjectStatus.QUEUED.value,
            CrmProjectStatus.IN_PROGRESS.value,
            CrmProjectStatus.CANCELLED.value,
        }
    ),
    CrmProjectStatus.COMPLETED.value: frozenset(),
    CrmProjectStatus.CANCELLED.value: frozenset(),
}


class CrmProjectNotFoundError(LookupError):
    pass


class CrmProjectStateError(ValueError):
    pass


class CrmProjectVersionConflictError(RuntimeError):
    pass


class CrmProjectService:
    def __init__(
        self,
        repository: CrmProjectRepository | None = None,
        material_repository: CrmMaterialRepository | None = None,
    ) -> None:
        self.repository = repository or CrmProjectRepository()
        self.materials = material_repository or CrmMaterialRepository()

    async def transition(
        self,
        session: AsyncSession,
        *,
        project_id: int,
        expected_version: int,
        to_status: CrmProjectStatus,
        reason_code: str,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmOrderProject:
        if expected_version <= 0:
            raise CrmProjectVersionConflictError("CRM project version must be positive")
        if not CRM_REASON_CODE_PATTERN.fullmatch(reason_code):
            raise CrmProjectStateError("CRM reason code has an invalid format")
        project = await self.repository.get_for_update(session, project_id=project_id)
        if project is None:
            raise CrmProjectNotFoundError("CRM project was not found")
        self._require_transition(project, expected_version, to_status)
        if to_status in {CrmProjectStatus.COMPLETED, CrmProjectStatus.CANCELLED}:
            units = await self.repository.list_units_for_update(
                session,
                project_id=project.id,
            )
            await self._require_terminal_aggregate(
                session,
                project=project,
                units=units,
                to_status=to_status,
            )

        current_time = ensure_utc(now or datetime.now(timezone.utc))
        previous_status = project.status
        project.status = to_status.value
        project.version += 1
        if to_status == CrmProjectStatus.IN_PROGRESS and project.started_at is None:
            project.started_at = current_time
        if to_status in {CrmProjectStatus.COMPLETED, CrmProjectStatus.CANCELLED}:
            project.closed_at = current_time
        self.repository.add_status_event(
            session,
            project,
            from_status=previous_status,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            now=current_time,
        )
        await session.flush()
        return project

    @staticmethod
    def _require_transition(
        project: CrmOrderProject,
        expected_version: int,
        to_status: CrmProjectStatus,
    ) -> None:
        if project.version != expected_version:
            raise CrmProjectVersionConflictError("CRM project version has changed")
        if to_status.value not in CRM_PROJECT_TRANSITIONS[project.status]:
            raise CrmProjectStateError(
                f"CRM project cannot transition from {project.status} to {to_status.value}"
            )

    async def _require_terminal_aggregate(
        self,
        session: AsyncSession,
        *,
        project: CrmOrderProject,
        units: list[CrmProductionUnit],
        to_status: CrmProjectStatus,
    ) -> None:
        if not units or len(units) != project.units_count:
            raise CrmProjectStateError("CRM project unit aggregate is inconsistent")
        required_unit_status = {
            CrmProjectStatus.COMPLETED: CrmProductionUnitStatus.COMPLETED.value,
            CrmProjectStatus.CANCELLED: CrmProductionUnitStatus.CANCELLED.value,
        }[to_status]
        if any(unit.status != required_unit_status for unit in units):
            raise CrmProjectStateError(
                f"All CRM project units must be {required_unit_status} before closure"
            )
        reservations = await self.materials.list_active_reservations_for_units(
            session,
            production_unit_ids=tuple(unit.id for unit in units),
        )
        if reservations:
            raise CrmProjectStateError("Active material reservations prevent CRM project closure")
