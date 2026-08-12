from __future__ import annotations

from collections.abc import Awaitable
from datetime import timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.crm.command_repository import (
    CrmCommandIdempotencyConflictError,
    CrmCommandInProgressError,
)
from app.modules.crm.command_schemas import (
    CrmAssignmentWrite,
    CrmProjectTransitionWrite,
    CrmStaffCommandReceipt,
    CrmUnitPlanWrite,
    CrmUnitTransitionWrite,
)
from app.modules.crm.command_security import (
    InvalidCrmIdempotencyKeyError,
    normalize_crm_idempotency_key,
)
from app.modules.crm.command_service import (
    CrmAssigneeNotEligibleError,
    CrmAssignmentStateError,
    CrmStaffCommandService,
)
from app.modules.crm.dependencies import require_crm_reader
from app.modules.crm.material_models import CrmMaterialMovement, CrmMaterialReservation
from app.modules.crm.material_schemas import (
    CrmMaterialAdjustmentWrite,
    CrmMaterialMovementReceipt,
    CrmMaterialQuantityWrite,
    CrmMaterialReservationWrite,
)
from app.modules.crm.material_service import (
    CrmMaterialConflictError,
    CrmMaterialNotFoundError,
    CrmMaterialService,
)
from app.modules.crm.models import CrmProjectStatus
from app.modules.crm.production_service import (
    CrmProductionConflictError,
    CrmProductionNotFoundError,
    CrmProductionVersionConflictError,
)
from app.modules.crm.read_schemas import (
    CrmFabricPage,
    CrmGarmentModelPage,
    CrmProjectDetail,
    CrmProjectPage,
)
from app.modules.crm.read_service import (
    CrmReadEvidenceError,
    CrmReadNotFoundError,
    CrmReadService,
)
from app.modules.crm.service import (
    CrmProjectNotFoundError,
    CrmProjectStateError,
    CrmProjectVersionConflictError,
)
from app.modules.identity.models import User

router = APIRouter(prefix="/api/crm", tags=["crm-staff"])
write_router = APIRouter(prefix="/api/crm", tags=["crm-staff-write"])


def get_crm_read_service(request: Request) -> CrmReadService:
    service = request.app.state.crm_read_service
    if not isinstance(service, CrmReadService):
        raise RuntimeError("CRM read service is not initialized")
    return service


def get_crm_command_service(request: Request) -> CrmStaffCommandService:
    service = request.app.state.crm_command_service
    if not isinstance(service, CrmStaffCommandService):
        raise RuntimeError("CRM command service is not initialized")
    return service


def get_crm_material_service(request: Request) -> CrmMaterialService:
    service = request.app.state.crm_material_service
    if not isinstance(service, CrmMaterialService):
        raise RuntimeError("CRM material service is not initialized")
    return service


@router.get("/projects", response_model=CrmProjectPage)
async def list_projects(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReadService, Depends(get_crm_read_service)],
    status: CrmProjectStatus | None = None,
    assigned_to_user_id: Annotated[int | None, Query(ge=1)] = None,
    cursor: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CrmProjectPage:
    _no_store(response)
    return await service.list_projects(
        session,
        status=status,
        assigned_to_user_id=assigned_to_user_id,
        cursor=cursor,
        limit=limit,
    )


@router.get("/projects/{project_id}", response_model=CrmProjectDetail)
async def get_project(
    project_id: Annotated[int, Path(ge=1)],
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReadService, Depends(get_crm_read_service)],
    unit_cursor: Annotated[int | None, Query(ge=1)] = None,
    unit_limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CrmProjectDetail:
    _no_store(response)
    try:
        return await service.get_project(
            session,
            project_id=project_id,
            unit_cursor=unit_cursor,
            unit_limit=unit_limit,
        )
    except CrmReadNotFoundError as error:
        raise HTTPException(status_code=404, detail="CRM project not found") from error
    except CrmReadEvidenceError as error:
        raise HTTPException(status_code=409, detail="CRM evidence is inconsistent") from error


@router.get("/reference/fabrics", response_model=CrmFabricPage)
async def list_fabrics(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReadService, Depends(get_crm_read_service)],
    is_active: bool | None = None,
    cursor: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CrmFabricPage:
    _no_store(response)
    return await service.list_fabrics(
        session,
        is_active=is_active,
        cursor=cursor,
        limit=limit,
    )


@router.get("/reference/garment-models", response_model=CrmGarmentModelPage)
async def list_garment_models(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReadService, Depends(get_crm_read_service)],
    is_active: bool | None = None,
    cursor: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CrmGarmentModelPage:
    _no_store(response)
    try:
        return await service.list_garment_models(
            session,
            is_active=is_active,
            cursor=cursor,
            limit=limit,
        )
    except CrmReadEvidenceError as error:
        raise HTTPException(status_code=409, detail="CRM evidence is inconsistent") from error


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@write_router.patch("/projects/{project_id}/status", response_model=CrmStaffCommandReceipt)
async def transition_project(
    project_id: Annotated[int, Path(ge=1)],
    payload: CrmProjectTransitionWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmStaffCommandService, Depends(get_crm_command_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmStaffCommandReceipt:
    _no_store(response)
    return await _execute_command(
        session,
        service.transition_project(
            session,
            project_id=project_id,
            expected_version=payload.expected_version,
            to_status=payload.to_status,
            reason_code=payload.reason_code,
            idempotency_key=idempotency_key,
            actor_user_id=actor.id,
        ),
    )


@write_router.put("/projects/{project_id}/assignment", response_model=CrmStaffCommandReceipt)
async def assign_project(
    project_id: Annotated[int, Path(ge=1)],
    payload: CrmAssignmentWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmStaffCommandService, Depends(get_crm_command_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmStaffCommandReceipt:
    _no_store(response)
    return await _execute_command(
        session,
        service.assign_project(
            session,
            project_id=project_id,
            expected_version=payload.expected_version,
            assigned_to_user_id=payload.assigned_to_user_id,
            reason_code=payload.reason_code,
            idempotency_key=idempotency_key,
            actor_user_id=actor.id,
        ),
    )


@write_router.patch("/units/{unit_id}/status", response_model=CrmStaffCommandReceipt)
async def transition_unit(
    unit_id: Annotated[int, Path(ge=1)],
    payload: CrmUnitTransitionWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmStaffCommandService, Depends(get_crm_command_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmStaffCommandReceipt:
    _no_store(response)
    return await _execute_command(
        session,
        service.transition_unit(
            session,
            production_unit_id=unit_id,
            expected_version=payload.expected_version,
            to_status=payload.to_status,
            reason_code=payload.reason_code,
            idempotency_key=idempotency_key,
            actor_user_id=actor.id,
        ),
    )


@write_router.post("/units/{unit_id}/plans", response_model=CrmStaffCommandReceipt)
async def plan_unit(
    unit_id: Annotated[int, Path(ge=1)],
    payload: CrmUnitPlanWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmStaffCommandService, Depends(get_crm_command_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmStaffCommandReceipt:
    _no_store(response)
    return await _execute_command(
        session,
        service.plan_unit(
            session,
            production_unit_id=unit_id,
            expected_version=payload.expected_version,
            garment_size_id=payload.garment_size_id,
            tech_card_revision_id=payload.tech_card_revision_id,
            idempotency_key=idempotency_key,
            actor_user_id=actor.id,
        ),
    )


@write_router.put("/units/{unit_id}/assignment", response_model=CrmStaffCommandReceipt)
async def assign_unit(
    unit_id: Annotated[int, Path(ge=1)],
    payload: CrmAssignmentWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmStaffCommandService, Depends(get_crm_command_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmStaffCommandReceipt:
    _no_store(response)
    return await _execute_command(
        session,
        service.assign_unit(
            session,
            production_unit_id=unit_id,
            expected_version=payload.expected_version,
            assigned_to_user_id=payload.assigned_to_user_id,
            reason_code=payload.reason_code,
            idempotency_key=idempotency_key,
            actor_user_id=actor.id,
        ),
    )


@write_router.post(
    "/materials/fabrics/{fabric_id}/receipts",
    response_model=CrmMaterialMovementReceipt,
)
async def receive_material(
    fabric_id: Annotated[int, Path(ge=1)],
    payload: CrmMaterialQuantityWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmMaterialService, Depends(get_crm_material_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmMaterialMovementReceipt:
    _no_store(response)
    return await _execute_material(
        session,
        service.receive(
            session,
            fabric_id=fabric_id,
            quantity_meters=payload.quantity_meters,
            idempotency_key=_material_key(idempotency_key),
            reason_code=payload.reason_code,
            actor_user_id=actor.id,
        ),
    )


@write_router.post(
    "/materials/fabrics/{fabric_id}/adjustments",
    response_model=CrmMaterialMovementReceipt,
)
async def adjust_material(
    fabric_id: Annotated[int, Path(ge=1)],
    payload: CrmMaterialAdjustmentWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmMaterialService, Depends(get_crm_material_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmMaterialMovementReceipt:
    _no_store(response)
    return await _execute_material(
        session,
        service.adjust(
            session,
            fabric_id=fabric_id,
            quantity_meters=payload.quantity_meters,
            direction=payload.direction,
            idempotency_key=_material_key(idempotency_key),
            reason_code=payload.reason_code,
            actor_user_id=actor.id,
        ),
    )


@write_router.post(
    "/materials/reservations",
    response_model=CrmMaterialMovementReceipt,
)
async def reserve_material(
    payload: CrmMaterialReservationWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmMaterialService, Depends(get_crm_material_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmMaterialMovementReceipt:
    _no_store(response)
    return await _execute_material_reservation(
        session,
        service.reserve(
            session,
            plan_revision_id=payload.plan_revision_id,
            fabric_id=payload.fabric_id,
            quantity_meters=payload.quantity_meters,
            idempotency_key=_material_key(idempotency_key),
            actor_user_id=actor.id,
        ),
    )


@write_router.post(
    "/materials/reservations/{reservation_id}/consume",
    response_model=CrmMaterialMovementReceipt,
)
async def consume_material(
    reservation_id: Annotated[int, Path(ge=1)],
    payload: CrmMaterialQuantityWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmMaterialService, Depends(get_crm_material_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmMaterialMovementReceipt:
    _no_store(response)
    return await _execute_material(
        session,
        service.consume(
            session,
            reservation_id=reservation_id,
            quantity_meters=payload.quantity_meters,
            idempotency_key=_material_key(idempotency_key),
            reason_code=payload.reason_code,
            actor_user_id=actor.id,
        ),
    )


@write_router.post(
    "/materials/reservations/{reservation_id}/release",
    response_model=CrmMaterialMovementReceipt,
)
async def release_material(
    reservation_id: Annotated[int, Path(ge=1)],
    payload: CrmMaterialQuantityWrite,
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmMaterialService, Depends(get_crm_material_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CrmMaterialMovementReceipt:
    _no_store(response)
    return await _execute_material(
        session,
        service.release(
            session,
            reservation_id=reservation_id,
            quantity_meters=payload.quantity_meters,
            idempotency_key=_material_key(idempotency_key),
            reason_code=payload.reason_code,
            actor_user_id=actor.id,
        ),
    )


async def _execute_command(
    session: AsyncSession,
    operation: Awaitable[CrmStaffCommandReceipt],
) -> CrmStaffCommandReceipt:
    try:
        receipt = await operation
    except InvalidCrmIdempotencyKeyError as error:
        raise HTTPException(status_code=400, detail="Invalid Idempotency-Key") from error
    except (CrmProjectNotFoundError, CrmProductionNotFoundError) as error:
        raise HTTPException(status_code=404, detail="CRM target not found") from error
    except (
        CrmAssigneeNotEligibleError,
        CrmAssignmentStateError,
        CrmCommandIdempotencyConflictError,
        CrmCommandInProgressError,
        CrmProjectStateError,
        CrmProjectVersionConflictError,
        CrmProductionConflictError,
        CrmProductionVersionConflictError,
    ) as error:
        raise HTTPException(status_code=409, detail="CRM command conflict") from error
    await session.commit()
    return receipt


async def _execute_material(
    session: AsyncSession,
    operation: Awaitable[CrmMaterialMovement],
) -> CrmMaterialMovementReceipt:
    try:
        movement = await operation
    except CrmMaterialNotFoundError as error:
        raise HTTPException(status_code=404, detail="CRM material target not found") from error
    except CrmMaterialConflictError as error:
        raise HTTPException(status_code=409, detail="CRM material command conflict") from error
    await session.commit()
    return _material_receipt(movement)


async def _execute_material_reservation(
    session: AsyncSession,
    operation: Awaitable[tuple[CrmMaterialReservation, CrmMaterialMovement]],
) -> CrmMaterialMovementReceipt:
    try:
        _, movement = await operation
    except CrmMaterialNotFoundError as error:
        raise HTTPException(status_code=404, detail="CRM material target not found") from error
    except CrmMaterialConflictError as error:
        raise HTTPException(status_code=409, detail="CRM material command conflict") from error
    await session.commit()
    return _material_receipt(movement)


def _material_key(value: str) -> str:
    try:
        return normalize_crm_idempotency_key(value)
    except InvalidCrmIdempotencyKeyError as error:
        raise HTTPException(status_code=400, detail="Invalid Idempotency-Key") from error


def _material_receipt(movement: CrmMaterialMovement) -> CrmMaterialMovementReceipt:
    if movement.id is None:
        raise RuntimeError("CRM material movement has no database ID")
    occurred_at = movement.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    else:
        occurred_at = occurred_at.astimezone(timezone.utc)
    return CrmMaterialMovementReceipt(
        movement_id=movement.id,
        fabric_id=movement.fabric_id,
        reservation_id=movement.reservation_id,
        movement_type=movement.movement_type,
        quantity_meters=movement.quantity_meters,
        balance_on_hand_after=movement.balance_on_hand_after,
        balance_reserved_after=movement.balance_reserved_after,
        balance_available_after=(movement.balance_on_hand_after - movement.balance_reserved_after),
        occurred_at=occurred_at,
    )
