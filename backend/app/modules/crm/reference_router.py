from __future__ import annotations

from collections.abc import Awaitable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.crm.dependencies import require_crm_reader
from app.modules.crm.reference_schemas import (
    CrmCatalogProductModelAssignmentRead,
    CrmCatalogProductModelAssignmentWrite,
    CrmFabricReferenceRead,
    CrmFabricUpdate,
    CrmFabricWrite,
    CrmGarmentModelReferenceRead,
    CrmGarmentModelUpdate,
    CrmGarmentModelWrite,
    CrmTechCardCreate,
    CrmTechCardRead,
    CrmTechCardRevisionCreate,
    CrmTechCardRevisionRead,
)
from app.modules.crm.reference_service import (
    CrmReferenceConflictError,
    CrmReferenceNotFoundError,
    CrmReferenceService,
    CrmReferenceVersionConflictError,
)
from app.modules.identity.models import User

router = APIRouter(prefix="/api/crm/reference", tags=["crm-reference-write"])
T = TypeVar("T")


def get_reference_service() -> CrmReferenceService:
    return CrmReferenceService()


async def _write(session: AsyncSession, operation: Awaitable[T]) -> T:
    try:
        result = await operation
        await session.commit()
        return result
    except CrmReferenceNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (CrmReferenceConflictError, CrmReferenceVersionConflictError) as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="CRM reference write conflict") from error


@router.post("/fabrics", response_model=CrmFabricReferenceRead, status_code=201)
async def create_fabric(
    payload: CrmFabricWrite,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReferenceService, Depends(get_reference_service)],
) -> CrmFabricReferenceRead:
    fabric = await _write(
        session,
        service.create_fabric(session, payload=payload, actor_user_id=actor.id),
    )
    return CrmFabricReferenceRead.model_validate(fabric)


@router.put("/fabrics/{fabric_id}", response_model=CrmFabricReferenceRead)
async def update_fabric(
    fabric_id: Annotated[int, Path(ge=1)],
    payload: CrmFabricUpdate,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReferenceService, Depends(get_reference_service)],
) -> CrmFabricReferenceRead:
    fabric = await _write(
        session,
        service.update_fabric(
            session,
            fabric_id=fabric_id,
            expected_version=payload.expected_version,
            payload=CrmFabricWrite.model_validate(payload.model_dump(exclude={"expected_version"})),
            actor_user_id=actor.id,
        ),
    )
    return CrmFabricReferenceRead.model_validate(fabric)


@router.post(
    "/garment-models",
    response_model=CrmGarmentModelReferenceRead,
    status_code=201,
)
async def create_garment_model(
    payload: CrmGarmentModelWrite,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReferenceService, Depends(get_reference_service)],
) -> CrmGarmentModelReferenceRead:
    model = await _write(
        session,
        service.create_garment_model(session, payload=payload, actor_user_id=actor.id),
    )
    return CrmGarmentModelReferenceRead.model_validate(model)


@router.put(
    "/garment-models/{garment_model_id}",
    response_model=CrmGarmentModelReferenceRead,
)
async def update_garment_model(
    garment_model_id: Annotated[int, Path(ge=1)],
    payload: CrmGarmentModelUpdate,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReferenceService, Depends(get_reference_service)],
) -> CrmGarmentModelReferenceRead:
    model = await _write(
        session,
        service.update_garment_model(
            session,
            garment_model_id=garment_model_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentModelWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
            actor_user_id=actor.id,
        ),
    )
    return CrmGarmentModelReferenceRead.model_validate(model)


@router.post(
    "/garment-models/{garment_model_id}/products",
    response_model=CrmCatalogProductModelAssignmentRead,
    status_code=201,
)
async def link_catalog_product(
    garment_model_id: Annotated[int, Path(ge=1)],
    payload: CrmCatalogProductModelAssignmentWrite,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReferenceService, Depends(get_reference_service)],
) -> CrmCatalogProductModelAssignmentRead:
    link = await _write(
        session,
        service.link_catalog_product(
            session,
            garment_model_id=garment_model_id,
            catalog_product_id=payload.catalog_product_id,
            actor_user_id=actor.id,
        ),
    )
    return CrmCatalogProductModelAssignmentRead(
        garment_model_id=link.garment_model_id,
        catalog_product_id=link.id,
    )


@router.post(
    "/garment-models/{garment_model_id}/tech-cards",
    response_model=CrmTechCardRead,
    status_code=201,
)
async def create_tech_card(
    garment_model_id: Annotated[int, Path(ge=1)],
    payload: CrmTechCardCreate,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReferenceService, Depends(get_reference_service)],
) -> CrmTechCardRead:
    card = await _write(
        session,
        service.create_tech_card(
            session,
            garment_model_id=garment_model_id,
            payload=payload,
            actor_user_id=actor.id,
        ),
    )
    return CrmTechCardRead.model_validate(card)


@router.post(
    "/tech-cards/{tech_card_id}/revisions",
    response_model=CrmTechCardRevisionRead,
    status_code=201,
)
async def create_tech_card_revision(
    tech_card_id: Annotated[int, Path(ge=1)],
    payload: CrmTechCardRevisionCreate,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReferenceService, Depends(get_reference_service)],
) -> CrmTechCardRevisionRead:
    revision = await _write(
        session,
        service.create_tech_card_revision(
            session,
            tech_card_id=tech_card_id,
            expected_latest_revision=payload.expected_latest_revision,
            payload=payload.revision,
            actor_user_id=actor.id,
        ),
    )
    return CrmTechCardRevisionRead.model_validate(revision)


@router.post(
    "/tech-cards/{tech_card_id}/revisions/{revision_number}/publish",
    response_model=CrmTechCardRevisionRead,
)
async def publish_tech_card_revision(
    tech_card_id: Annotated[int, Path(ge=1)],
    revision_number: Annotated[int, Path(ge=1)],
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReferenceService, Depends(get_reference_service)],
) -> CrmTechCardRevisionRead:
    revision = await _write(
        session,
        service.publish_tech_card_revision(
            session,
            tech_card_id=tech_card_id,
            revision_number=revision_number,
            actor_user_id=actor.id,
        ),
    )
    return CrmTechCardRevisionRead.model_validate(revision)


@router.post(
    "/tech-cards/{tech_card_id}/revisions/{revision_number}/discard",
    response_model=CrmTechCardRevisionRead,
)
async def discard_tech_card_revision(
    tech_card_id: Annotated[int, Path(ge=1)],
    revision_number: Annotated[int, Path(ge=1)],
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmReferenceService, Depends(get_reference_service)],
) -> CrmTechCardRevisionRead:
    revision = await _write(
        session,
        service.discard_tech_card_draft(
            session,
            tech_card_id=tech_card_id,
            revision_number=revision_number,
            actor_user_id=actor.id,
        ),
    )
    return CrmTechCardRevisionRead.model_validate(revision)
