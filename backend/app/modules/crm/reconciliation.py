from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.minio import MinioStorage
from app.modules.crm.command_models import CrmStaffCommandStatus
from app.modules.crm.material_models import (
    CrmMaterialMovement,
    CrmMaterialMovementType,
    CrmMaterialReservationStatus,
)
from app.modules.crm.models import CrmProductionUnitStatus, CrmProjectStatus
from app.modules.crm.reconciliation_repository import (
    CrmReconciliationData,
    CrmReconciliationRepository,
)
from app.modules.identity.security import ensure_utc
from app.modules.media.models import MediaStatus

ZERO = Decimal("0.000")


class CrmReconciliationStorageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CrmReconciliationIssue:
    code: str
    entity_type: str
    entity_id: int

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
        }


@dataclass(frozen=True, slots=True)
class CrmReconciliationReport:
    checked_at: datetime
    object_verification: str
    counts: dict[str, int]
    issues: tuple[CrmReconciliationIssue, ...]
    total_issues: int

    @property
    def healthy(self) -> bool:
        return self.total_issues == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "healthy": self.healthy,
            "checked_at": self.checked_at.isoformat().replace("+00:00", "Z"),
            "object_verification": self.object_verification,
            "counts": self.counts,
            "total_issues": self.total_issues,
            "issues_truncated": self.total_issues > len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
        }


class _IssueCollector:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.total = 0
        self.items: list[CrmReconciliationIssue] = []

    def add(self, code: str, entity_type: str, entity_id: int) -> None:
        self.total += 1
        if len(self.items) < self.limit:
            self.items.append(
                CrmReconciliationIssue(
                    code=code,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
            )


class CrmReconciliationService:
    def __init__(
        self,
        repository: CrmReconciliationRepository | None = None,
    ) -> None:
        self.repository = repository or CrmReconciliationRepository()

    async def inspect(
        self,
        session: AsyncSession,
        *,
        private_bucket: str,
        storage: MinioStorage | None = None,
        max_issues: int = 1_000,
        stale_after_seconds: int = 900,
        now: datetime | None = None,
    ) -> CrmReconciliationReport:
        if not 1 <= max_issues <= 10_000:
            raise ValueError("CRM reconciliation max issues must be between 1 and 10000")
        if stale_after_seconds < 60:
            raise ValueError("CRM reconciliation stale threshold must be at least 60 seconds")
        checked_at = ensure_utc(now or datetime.now(timezone.utc))
        await self._begin_consistent_snapshot(session)
        data = await self.repository.load(session, private_bucket=private_bucket)
        issues = _IssueCollector(max_issues)
        self._inspect_projects(data, issues)
        self._inspect_materials(data, issues)
        await self._inspect_files(
            data,
            issues,
            private_bucket,
            storage,
            checked_at,
            stale_after_seconds,
        )
        self._inspect_commands(data, issues, checked_at, stale_after_seconds)
        return CrmReconciliationReport(
            checked_at=checked_at,
            object_verification="performed" if storage is not None else "skipped",
            counts={
                "projects": len(data.projects),
                "units": len(data.units),
                "material_balances": len(data.balances),
                "material_reservations": len(data.reservations),
                "material_movements": len(data.movements),
                "file_attachments": len(data.attachments),
                "private_media": len(data.private_media),
                "staff_commands": len(data.commands),
            },
            issues=tuple(issues.items),
            total_issues=issues.total,
        )

    @staticmethod
    async def _begin_consistent_snapshot(session: AsyncSession) -> None:
        if session.get_bind().dialect.name != "postgresql":
            return
        if session.in_transaction():
            raise RuntimeError(
                "CRM reconciliation must be the first operation in its database session"
            )
        connection = await session.connection(
            execution_options={"isolation_level": "REPEATABLE READ"}
        )
        await connection.execute(text("SET TRANSACTION READ ONLY"))

    @staticmethod
    def _inspect_projects(data: CrmReconciliationData, issues: _IssueCollector) -> None:
        units_by_project: dict[int, list] = defaultdict(list)
        for unit in data.units:
            units_by_project[unit.project_id].append(unit)
        project_events: dict[int, list] = defaultdict(list)
        unit_events: dict[int, list] = defaultdict(list)
        project_assignments: dict[int, list] = defaultdict(list)
        unit_assignments: dict[int, list] = defaultdict(list)
        for event in data.project_events:
            project_events[event.project_id].append(event)
        for event in data.unit_events:
            unit_events[event.production_unit_id].append(event)
        for event in data.assignment_events:
            if event.production_project_id is not None:
                project_assignments[event.production_project_id].append(event)
            elif event.production_unit_id is not None:
                unit_assignments[event.production_unit_id].append(event)

        plan_unit = {plan.id: plan.production_unit_id for plan in data.plans}
        active_reservation_units = {
            plan_unit.get(reservation.production_plan_revision_id)
            for reservation in data.reservations
            if reservation.status == CrmMaterialReservationStatus.ACTIVE.value
        }

        for project in data.projects:
            units = units_by_project[project.id]
            if len(units) != project.units_count:
                issues.add("project_unit_count_drift", "project", project.id)
            if len({unit.order_item_id for unit in units}) != project.items_count:
                issues.add("project_item_count_drift", "project", project.id)
            status_events = project_events[project.id]
            assignments = project_assignments[project.id]
            versions = [event.version for event in status_events] + [
                event.entity_version for event in assignments
            ]
            if sorted(versions) != list(range(1, project.version + 1)):
                issues.add("project_version_history_drift", "project", project.id)
            if not status_events or status_events[-1].to_status != project.status:
                issues.add("project_status_event_drift", "project", project.id)
            expected_assignee = assignments[-1].to_assigned_to_user_id if assignments else None
            if expected_assignee != project.assigned_to_user_id:
                issues.add("project_assignment_event_drift", "project", project.id)
            if project.status == CrmProjectStatus.COMPLETED.value and any(
                unit.status != CrmProductionUnitStatus.COMPLETED.value for unit in units
            ):
                issues.add("completed_project_unit_drift", "project", project.id)
            if project.status == CrmProjectStatus.CANCELLED.value and any(
                unit.status != CrmProductionUnitStatus.CANCELLED.value for unit in units
            ):
                issues.add("cancelled_project_unit_drift", "project", project.id)
            if project.status in {
                CrmProjectStatus.COMPLETED.value,
                CrmProjectStatus.CANCELLED.value,
            } and any(unit.id in active_reservation_units for unit in units):
                issues.add("terminal_project_reservation_drift", "project", project.id)

        active_plans_by_unit: dict[int, int] = defaultdict(int)
        for plan in data.plans:
            if plan.status == "active":
                active_plans_by_unit[plan.production_unit_id] += 1
        for unit in data.units:
            status_events = unit_events[unit.id]
            assignments = unit_assignments[unit.id]
            versions = [event.version for event in status_events] + [
                event.entity_version for event in assignments
            ]
            if sorted(versions) != list(range(1, unit.version + 1)):
                issues.add("unit_version_history_drift", "unit", unit.id)
            if not status_events or status_events[-1].to_status != unit.status:
                issues.add("unit_status_event_drift", "unit", unit.id)
            expected_assignee = assignments[-1].to_assigned_to_user_id if assignments else None
            if expected_assignee != unit.assigned_to_user_id:
                issues.add("unit_assignment_event_drift", "unit", unit.id)
            if (
                unit.status
                in {
                    CrmProductionUnitStatus.IN_PROGRESS.value,
                    CrmProductionUnitStatus.QUALITY_CONTROL.value,
                    CrmProductionUnitStatus.COMPLETED.value,
                }
                and active_plans_by_unit[unit.id] != 1
            ):
                issues.add("active_unit_plan_drift", "unit", unit.id)
            if (
                unit.status
                in {
                    CrmProductionUnitStatus.COMPLETED.value,
                    CrmProductionUnitStatus.CANCELLED.value,
                }
                and unit.id in active_reservation_units
            ):
                issues.add("terminal_unit_reservation_drift", "unit", unit.id)

    @classmethod
    def _inspect_materials(
        cls,
        data: CrmReconciliationData,
        issues: _IssueCollector,
    ) -> None:
        balances = {balance.fabric_id: balance for balance in data.balances}
        movements_by_fabric: dict[int, list[CrmMaterialMovement]] = defaultdict(list)
        active_reserved_by_fabric: dict[int, Decimal] = defaultdict(lambda: ZERO)
        movements_by_reservation: dict[int, list[CrmMaterialMovement]] = defaultdict(list)
        for movement in data.movements:
            movements_by_fabric[movement.fabric_id].append(movement)
            if movement.reservation_id is not None:
                movements_by_reservation[movement.reservation_id].append(movement)
        for reservation in data.reservations:
            if reservation.status == CrmMaterialReservationStatus.ACTIVE.value:
                active_reserved_by_fabric[reservation.fabric_id] += reservation.remaining_meters

        fabric_ids = sorted(
            set(balances) | set(movements_by_fabric) | set(active_reserved_by_fabric)
        )
        for fabric_id in fabric_ids:
            balance = balances.get(fabric_id)
            movements = movements_by_fabric[fabric_id]
            if balance is None:
                issues.add("material_balance_missing", "fabric", fabric_id)
                continue
            on_hand, reserved = cls._replay_material_movements(movements, issues)
            if movements and (
                balance.on_hand_meters != on_hand or balance.reserved_meters != reserved
            ):
                issues.add("material_balance_projection_drift", "fabric", fabric_id)
            if balance.version != len(movements) + 1:
                issues.add("material_balance_version_drift", "fabric", fabric_id)
            if balance.reserved_meters != active_reserved_by_fabric[fabric_id]:
                issues.add("material_active_reservation_drift", "fabric", fabric_id)

        for reservation in data.reservations:
            movements = movements_by_reservation[reservation.id]
            reserved = sum(
                (
                    movement.quantity_meters
                    for movement in movements
                    if movement.movement_type == CrmMaterialMovementType.RESERVE.value
                ),
                ZERO,
            )
            consumed = sum(
                (
                    movement.quantity_meters
                    for movement in movements
                    if movement.movement_type == CrmMaterialMovementType.CONSUME.value
                ),
                ZERO,
            )
            released = sum(
                (
                    movement.quantity_meters
                    for movement in movements
                    if movement.movement_type == CrmMaterialMovementType.RELEASE.value
                ),
                ZERO,
            )
            if (
                reserved != reservation.requested_meters
                or consumed != reservation.consumed_meters
                or released != reservation.released_meters
            ):
                issues.add("material_reservation_movement_drift", "reservation", reservation.id)

    @staticmethod
    def _replay_material_movements(
        movements: list[CrmMaterialMovement],
        issues: _IssueCollector,
    ) -> tuple[Decimal, Decimal]:
        on_hand = ZERO
        reserved = ZERO
        for movement in movements:
            quantity = movement.quantity_meters
            if movement.movement_type in {
                CrmMaterialMovementType.RECEIPT.value,
                CrmMaterialMovementType.ADJUSTMENT_IN.value,
            }:
                on_hand += quantity
            elif movement.movement_type == CrmMaterialMovementType.ADJUSTMENT_OUT.value:
                on_hand -= quantity
            elif movement.movement_type == CrmMaterialMovementType.RESERVE.value:
                reserved += quantity
            elif movement.movement_type == CrmMaterialMovementType.RELEASE.value:
                reserved -= quantity
            elif movement.movement_type == CrmMaterialMovementType.CONSUME.value:
                on_hand -= quantity
                reserved -= quantity
            if (
                movement.balance_on_hand_after != on_hand
                or movement.balance_reserved_after != reserved
                or on_hand < ZERO
                or reserved < ZERO
                or reserved > on_hand
            ):
                issues.add("material_movement_snapshot_drift", "movement", movement.id)
        return on_hand, reserved

    @staticmethod
    async def _inspect_files(
        data: CrmReconciliationData,
        issues: _IssueCollector,
        private_bucket: str,
        storage: MinioStorage | None,
        checked_at: datetime,
        stale_after_seconds: int,
    ) -> None:
        attachment_media_ids = {attachment.media_object_id for attachment in data.attachments}
        for attachment in data.attachments:
            media = attachment.media
            if (
                media.status != MediaStatus.READY.value
                or media.is_public
                or media.bucket_name != private_bucket
            ):
                issues.add("crm_file_media_evidence_drift", "attachment", attachment.id)
                continue
            if storage is not None:
                try:
                    exists = await storage.private_crm_object_exists(media.object_key)
                except Exception as error:
                    raise CrmReconciliationStorageError(
                        "Private CRM object verification failed"
                    ) from error
                if not exists:
                    issues.add("crm_file_object_missing", "attachment", attachment.id)

        stale_before = checked_at - timedelta(seconds=stale_after_seconds)
        for media in data.private_media:
            if media.status == MediaStatus.READY.value and media.id not in attachment_media_ids:
                issues.add("crm_private_media_orphan", "media", media.id)
            if (
                media.status == MediaStatus.PENDING.value
                and ensure_utc(media.created_at) <= stale_before
            ):
                issues.add("crm_private_media_stale_pending", "media", media.id)

    @staticmethod
    def _inspect_commands(
        data: CrmReconciliationData,
        issues: _IssueCollector,
        checked_at: datetime,
        stale_after_seconds: int,
    ) -> None:
        stale_before = checked_at - timedelta(seconds=stale_after_seconds)
        for command in data.commands:
            if (
                command.status == CrmStaffCommandStatus.PROCESSING.value
                and ensure_utc(command.created_at) <= stale_before
            ):
                issues.add("crm_staff_command_stale_processing", "command", command.id)
