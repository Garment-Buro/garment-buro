from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import (
    CrmOrderProject,
    CrmProductionUnitStatus,
    CrmProjectStatus,
)
from app.modules.crm.read_repository import (
    CrmReadRepository,
    CrmUnitEvidence,
)
from app.modules.crm.read_schemas import (
    CrmProductionPlanSummary,
    CrmProductionUnitPage,
    CrmProductionUnitRead,
    CrmProjectDetail,
    CrmProjectPage,
    CrmProjectSummary,
)
from app.modules.identity.security import ensure_utc


class CrmReadNotFoundError(LookupError):
    pass


class CrmReadEvidenceError(RuntimeError):
    pass


class CrmReadService:
    def __init__(self, repository: CrmReadRepository | None = None) -> None:
        self.repository = repository or CrmReadRepository()

    async def list_projects(
        self,
        session: AsyncSession,
        *,
        status: CrmProjectStatus | None,
        assigned_to_user_id: int | None,
        cursor: int | None,
        limit: int,
    ) -> CrmProjectPage:
        projects, next_cursor = await self.repository.list_projects(
            session,
            status=status.value if status is not None else None,
            assigned_to_user_id=assigned_to_user_id,
            cursor=cursor,
            limit=limit,
        )
        return CrmProjectPage(
            items=[self._project(project) for project in projects],
            next_cursor=next_cursor,
            limit=limit,
        )

    async def get_project(
        self,
        session: AsyncSession,
        *,
        project_id: int,
        unit_cursor: int | None,
        unit_limit: int,
    ) -> CrmProjectDetail:
        project = await self.repository.get_project(session, project_id=project_id)
        if project is None:
            raise CrmReadNotFoundError("CRM project was not found")
        actual_units = await self.repository.count_project_units(
            session,
            project_id=project_id,
        )
        if actual_units != project.units_count:
            raise CrmReadEvidenceError("CRM project unit evidence is inconsistent")
        evidence, next_cursor = await self.repository.list_project_units(
            session,
            project_id=project_id,
            cursor=unit_cursor,
            limit=unit_limit,
        )
        return CrmProjectDetail(
            project=self._project(project),
            units=CrmProductionUnitPage(
                items=[self._unit(row) for row in evidence],
                next_cursor=next_cursor,
                limit=unit_limit,
            ),
        )

    @staticmethod
    def _project(project: CrmOrderProject) -> CrmProjectSummary:
        return CrmProjectSummary(
            id=project.id,
            order_id=project.order_id,
            status=CrmProjectStatus(project.status),
            version=project.version,
            items_count=project.items_count,
            units_count=project.units_count,
            assigned_to_user_id=project.assigned_to_user_id,
            paid_at=ensure_utc(project.payment_succeeded_at_snapshot),
            started_at=ensure_utc(project.started_at) if project.started_at is not None else None,
            closed_at=ensure_utc(project.closed_at) if project.closed_at is not None else None,
            created_at=ensure_utc(project.created_at),
            updated_at=ensure_utc(project.updated_at),
        )

    @staticmethod
    def _unit(evidence: CrmUnitEvidence) -> CrmProductionUnitRead:
        unit = evidence.unit
        item = evidence.order_item
        if item is None:
            raise CrmReadEvidenceError("CRM production unit order evidence is missing")
        plan = evidence.active_plan
        return CrmProductionUnitRead(
            id=unit.id,
            order_item_id=unit.order_item_id,
            product_id=unit.product_id_snapshot,
            variant_id=unit.variant_id_snapshot,
            unit_number=unit.unit_number,
            title=item.title_snapshot,
            sku=item.sku_snapshot,
            size=item.size_snapshot,
            color=item.color_snapshot,
            status=CrmProductionUnitStatus(unit.status),
            version=unit.version,
            assigned_to_user_id=unit.assigned_to_user_id,
            started_at=ensure_utc(unit.started_at) if unit.started_at is not None else None,
            closed_at=ensure_utc(unit.closed_at) if unit.closed_at is not None else None,
            created_at=ensure_utc(unit.created_at),
            updated_at=ensure_utc(unit.updated_at),
            active_plan=(
                CrmProductionPlanSummary(
                    id=plan.id,
                    revision_number=plan.revision_number,
                    garment_model_id=plan.garment_model_id,
                    garment_size_id=plan.garment_size_id,
                    tech_card_revision_id=plan.tech_card_revision_id,
                    planned_at=ensure_utc(plan.planned_at),
                )
                if plan is not None
                else None
            ),
        )
