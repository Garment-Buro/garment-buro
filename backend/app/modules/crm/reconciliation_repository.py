from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.crm.command_models import CrmAssignmentEvent, CrmStaffCommand
from app.modules.crm.file_models import CrmFileAttachment
from app.modules.crm.material_models import (
    CrmMaterialBalance,
    CrmMaterialMovement,
    CrmMaterialReservation,
)
from app.modules.crm.models import (
    CrmOrderProject,
    CrmProductionUnit,
    CrmProjectEvent,
)
from app.modules.crm.production_models import (
    CrmProductionPlanRevision,
    CrmProductionUnitEvent,
)
from app.modules.media.models import MediaObject


@dataclass(frozen=True, slots=True)
class CrmReconciliationData:
    projects: tuple[CrmOrderProject, ...]
    units: tuple[CrmProductionUnit, ...]
    project_events: tuple[CrmProjectEvent, ...]
    unit_events: tuple[CrmProductionUnitEvent, ...]
    assignment_events: tuple[CrmAssignmentEvent, ...]
    plans: tuple[CrmProductionPlanRevision, ...]
    balances: tuple[CrmMaterialBalance, ...]
    reservations: tuple[CrmMaterialReservation, ...]
    movements: tuple[CrmMaterialMovement, ...]
    commands: tuple[CrmStaffCommand, ...]
    attachments: tuple[CrmFileAttachment, ...]
    private_media: tuple[MediaObject, ...]


class CrmReconciliationRepository:
    async def load(
        self,
        session: AsyncSession,
        *,
        private_bucket: str,
    ) -> CrmReconciliationData:
        return CrmReconciliationData(
            projects=tuple(
                await session.scalars(select(CrmOrderProject).order_by(CrmOrderProject.id))
            ),
            units=tuple(
                await session.scalars(select(CrmProductionUnit).order_by(CrmProductionUnit.id))
            ),
            project_events=tuple(
                await session.scalars(
                    select(CrmProjectEvent).order_by(
                        CrmProjectEvent.project_id,
                        CrmProjectEvent.version,
                    )
                )
            ),
            unit_events=tuple(
                await session.scalars(
                    select(CrmProductionUnitEvent).order_by(
                        CrmProductionUnitEvent.production_unit_id,
                        CrmProductionUnitEvent.version,
                    )
                )
            ),
            assignment_events=tuple(
                await session.scalars(select(CrmAssignmentEvent).order_by(CrmAssignmentEvent.id))
            ),
            plans=tuple(
                await session.scalars(
                    select(CrmProductionPlanRevision).order_by(CrmProductionPlanRevision.id)
                )
            ),
            balances=tuple(
                await session.scalars(
                    select(CrmMaterialBalance).order_by(CrmMaterialBalance.fabric_id)
                )
            ),
            reservations=tuple(
                await session.scalars(
                    select(CrmMaterialReservation).order_by(CrmMaterialReservation.id)
                )
            ),
            movements=tuple(
                await session.scalars(
                    select(CrmMaterialMovement).order_by(
                        CrmMaterialMovement.fabric_id,
                        CrmMaterialMovement.id,
                    )
                )
            ),
            commands=tuple(
                await session.scalars(select(CrmStaffCommand).order_by(CrmStaffCommand.id))
            ),
            attachments=tuple(
                await session.scalars(
                    select(CrmFileAttachment)
                    .options(selectinload(CrmFileAttachment.media))
                    .order_by(CrmFileAttachment.id)
                )
            ),
            private_media=tuple(
                await session.scalars(
                    select(MediaObject)
                    .where(MediaObject.bucket_name == private_bucket)
                    .order_by(MediaObject.id)
                )
            ),
        )
