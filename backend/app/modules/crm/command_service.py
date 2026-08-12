from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.command_models import (
    CrmAssignmentEvent,
    CrmStaffCommand,
    CrmStaffCommandType,
)
from app.modules.crm.command_repository import CrmCommandRepository
from app.modules.crm.command_schemas import CrmStaffCommandReceipt
from app.modules.crm.command_security import normalize_crm_idempotency_key
from app.modules.crm.models import (
    CrmOrderProject,
    CrmProductionUnit,
    CrmProductionUnitStatus,
    CrmProjectStatus,
)
from app.modules.crm.production_repository import CrmProductionRepository
from app.modules.crm.production_service import (
    CrmProductionNotFoundError,
    CrmProductionService,
    CrmProductionVersionConflictError,
)
from app.modules.crm.repository import CrmProjectRepository
from app.modules.crm.service import (
    CRM_REASON_CODE_PATTERN,
    CrmProjectNotFoundError,
    CrmProjectService,
    CrmProjectVersionConflictError,
)
from app.modules.identity.models import PermissionCode
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import ensure_utc


class CrmAssigneeNotEligibleError(ValueError):
    pass


class CrmAssignmentStateError(ValueError):
    pass


class CrmStaffCommandService:
    def __init__(
        self,
        *,
        command_repository: CrmCommandRepository | None = None,
        project_repository: CrmProjectRepository | None = None,
        production_repository: CrmProductionRepository | None = None,
        identity_repository: IdentityRepository | None = None,
        project_service: CrmProjectService | None = None,
        production_service: CrmProductionService | None = None,
    ) -> None:
        self.commands = command_repository or CrmCommandRepository()
        self.projects = project_repository or CrmProjectRepository()
        self.production = production_repository or CrmProductionRepository()
        self.identity = identity_repository or IdentityRepository()
        self.project_service = project_service or CrmProjectService(self.projects)
        self.production_service = production_service or CrmProductionService(self.production)

    async def transition_project(
        self,
        session: AsyncSession,
        *,
        project_id: int,
        expected_version: int,
        to_status: CrmProjectStatus,
        reason_code: str,
        idempotency_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> CrmStaffCommandReceipt:
        occurred_at = self._now(now)
        command, replayed = await self._acquire(
            session,
            command_type=CrmStaffCommandType.PROJECT_TRANSITION,
            target_id=project_id,
            payload={
                "expected_version": expected_version,
                "to_status": to_status.value,
                "reason_code": reason_code,
            },
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        if replayed:
            return self._receipt(command)
        project = await self.project_service.transition(
            session,
            project_id=project_id,
            expected_version=expected_version,
            to_status=to_status,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        await self.commands.complete(
            session,
            command,
            result_version=project.version,
            now=occurred_at,
        )
        return self._receipt(command)

    async def transition_unit(
        self,
        session: AsyncSession,
        *,
        production_unit_id: int,
        expected_version: int,
        to_status: CrmProductionUnitStatus,
        reason_code: str,
        idempotency_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> CrmStaffCommandReceipt:
        occurred_at = self._now(now)
        command, replayed = await self._acquire(
            session,
            command_type=CrmStaffCommandType.UNIT_TRANSITION,
            target_id=production_unit_id,
            payload={
                "expected_version": expected_version,
                "to_status": to_status.value,
                "reason_code": reason_code,
            },
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        if replayed:
            return self._receipt(command)
        unit = await self.production_service.transition_unit(
            session,
            production_unit_id=production_unit_id,
            expected_version=expected_version,
            to_status=to_status,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        await self.commands.complete(
            session,
            command,
            result_version=unit.version,
            now=occurred_at,
        )
        return self._receipt(command)

    async def plan_unit(
        self,
        session: AsyncSession,
        *,
        production_unit_id: int,
        expected_version: int,
        garment_size_id: int | None,
        tech_card_revision_id: int,
        idempotency_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> CrmStaffCommandReceipt:
        occurred_at = self._now(now)
        command, replayed = await self._acquire(
            session,
            command_type=CrmStaffCommandType.UNIT_PLAN,
            target_id=production_unit_id,
            payload={
                "expected_version": expected_version,
                "garment_size_id": garment_size_id,
                "tech_card_revision_id": tech_card_revision_id,
            },
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        if replayed:
            return self._receipt(command)
        await self.production_service.plan_unit(
            session,
            production_unit_id=production_unit_id,
            expected_version=expected_version,
            garment_size_id=garment_size_id,
            tech_card_revision_id=tech_card_revision_id,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        unit = await self.production.get_unit_for_update(
            session,
            production_unit_id=production_unit_id,
        )
        if unit is None:
            raise CrmProductionNotFoundError("CRM production unit was not found")
        await self.commands.complete(
            session,
            command,
            result_version=unit.version,
            now=occurred_at,
        )
        return self._receipt(command)

    async def assign_project(
        self,
        session: AsyncSession,
        *,
        project_id: int,
        expected_version: int,
        assigned_to_user_id: int | None,
        reason_code: str,
        idempotency_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> CrmStaffCommandReceipt:
        occurred_at = self._now(now)
        command, replayed = await self._acquire(
            session,
            command_type=CrmStaffCommandType.PROJECT_ASSIGN,
            target_id=project_id,
            payload={
                "expected_version": expected_version,
                "assigned_to_user_id": assigned_to_user_id,
                "reason_code": reason_code,
            },
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        if replayed:
            return self._receipt(command)
        await self._require_assignee(session, assigned_to_user_id)
        project = await self.projects.get_for_update(session, project_id=project_id)
        if project is None:
            raise CrmProjectNotFoundError("CRM project was not found")
        self._require_project_assignment(project, expected_version, assigned_to_user_id)
        previous = project.assigned_to_user_id
        project.assigned_to_user_id = assigned_to_user_id
        project.version += 1
        await self._record_assignment(
            session,
            project=project,
            unit=None,
            previous=previous,
            assigned_to_user_id=assigned_to_user_id,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        await self.commands.complete(
            session,
            command,
            result_version=project.version,
            now=occurred_at,
        )
        return self._receipt(command)

    async def assign_unit(
        self,
        session: AsyncSession,
        *,
        production_unit_id: int,
        expected_version: int,
        assigned_to_user_id: int | None,
        reason_code: str,
        idempotency_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> CrmStaffCommandReceipt:
        occurred_at = self._now(now)
        command, replayed = await self._acquire(
            session,
            command_type=CrmStaffCommandType.UNIT_ASSIGN,
            target_id=production_unit_id,
            payload={
                "expected_version": expected_version,
                "assigned_to_user_id": assigned_to_user_id,
                "reason_code": reason_code,
            },
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        if replayed:
            return self._receipt(command)
        await self._require_assignee(session, assigned_to_user_id)
        unit = await self.production.get_unit_for_update(
            session,
            production_unit_id=production_unit_id,
        )
        if unit is None:
            raise CrmProductionNotFoundError("CRM production unit was not found")
        self._require_unit_assignment(unit, expected_version, assigned_to_user_id)
        previous = unit.assigned_to_user_id
        unit.assigned_to_user_id = assigned_to_user_id
        unit.version += 1
        await self._record_assignment(
            session,
            project=None,
            unit=unit,
            previous=previous,
            assigned_to_user_id=assigned_to_user_id,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            now=occurred_at,
        )
        await self.commands.complete(
            session,
            command,
            result_version=unit.version,
            now=occurred_at,
        )
        return self._receipt(command)

    async def _acquire(
        self,
        session: AsyncSession,
        *,
        command_type: CrmStaffCommandType,
        target_id: int,
        payload: dict[str, object],
        idempotency_key: str,
        actor_user_id: int,
        now: datetime,
    ) -> tuple[CrmStaffCommand, bool]:
        if actor_user_id <= 0:
            raise ValueError("CRM staff command requires an authenticated actor")
        normalized_key = normalize_crm_idempotency_key(idempotency_key)
        key_digest = hashlib.sha256(normalized_key.encode()).hexdigest()
        command_digest = self._command_digest(
            command_type=command_type.value,
            target_id=target_id,
            actor_user_id=actor_user_id,
            payload=payload,
        )
        return await self.commands.acquire(
            session,
            idempotency_key_sha256=key_digest,
            command_sha256=command_digest,
            command_type=command_type.value,
            target_id=target_id,
            actor_user_id=actor_user_id,
            now=now,
        )

    async def _require_assignee(
        self,
        session: AsyncSession,
        assigned_to_user_id: int | None,
    ) -> None:
        if assigned_to_user_id is None:
            return
        if not await self.identity.user_has_permission(
            session,
            user_id=assigned_to_user_id,
            permission=PermissionCode.CRM_ACCESS,
        ):
            raise CrmAssigneeNotEligibleError("CRM assignee must be an active CRM user")

    @staticmethod
    def _require_project_assignment(
        project: CrmOrderProject,
        expected_version: int,
        assigned_to_user_id: int | None,
    ) -> None:
        if expected_version <= 0 or project.version != expected_version:
            raise CrmProjectVersionConflictError("CRM project version has changed")
        if project.status in {CrmProjectStatus.COMPLETED.value, CrmProjectStatus.CANCELLED.value}:
            raise CrmAssignmentStateError("Closed CRM project cannot be reassigned")
        if project.assigned_to_user_id == assigned_to_user_id:
            raise CrmAssignmentStateError("CRM project assignment is unchanged")

    @staticmethod
    def _require_unit_assignment(
        unit: CrmProductionUnit,
        expected_version: int,
        assigned_to_user_id: int | None,
    ) -> None:
        if expected_version <= 0 or unit.version != expected_version:
            raise CrmProductionVersionConflictError("CRM production unit version has changed")
        if unit.status in {
            CrmProductionUnitStatus.COMPLETED.value,
            CrmProductionUnitStatus.CANCELLED.value,
        }:
            raise CrmAssignmentStateError("Closed CRM production unit cannot be reassigned")
        if unit.assigned_to_user_id == assigned_to_user_id:
            raise CrmAssignmentStateError("CRM production unit assignment is unchanged")

    async def _record_assignment(
        self,
        session: AsyncSession,
        *,
        project: CrmOrderProject | None,
        unit: CrmProductionUnit | None,
        previous: int | None,
        assigned_to_user_id: int | None,
        reason_code: str,
        actor_user_id: int,
        now: datetime,
    ) -> None:
        if not CRM_REASON_CODE_PATTERN.fullmatch(reason_code):
            raise CrmAssignmentStateError("CRM reason code has an invalid format")
        target = project or unit
        if target is None:
            raise RuntimeError("CRM assignment target is missing")
        target_name = "project" if project is not None else "unit"
        await self.commands.add_assignment_event(
            session,
            CrmAssignmentEvent(
                production_project_id=project.id if project is not None else None,
                production_unit_id=unit.id if unit is not None else None,
                event_key=f"{target_name}:{target.id}:assignment:version:{target.version}",
                entity_version=target.version,
                from_assigned_to_user_id=previous,
                to_assigned_to_user_id=assigned_to_user_id,
                reason_code=reason_code,
                actor_user_id=actor_user_id,
                occurred_at=now,
            ),
        )

    @staticmethod
    def _receipt(command: CrmStaffCommand) -> CrmStaffCommandReceipt:
        if command.id is None or command.result_version is None:
            raise RuntimeError("Completed CRM staff command has no result evidence")
        return CrmStaffCommandReceipt(
            command_id=command.id,
            command_type=command.command_type,
            target_id=command.target_id,
            result_version=command.result_version,
        )

    @staticmethod
    def _command_digest(**values: object) -> str:
        canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        return ensure_utc(value or datetime.now(timezone.utc))
