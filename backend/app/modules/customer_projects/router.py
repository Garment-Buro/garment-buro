from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError

from app.modules.customer_projects.dependencies import CurrentUser, ResourceId, Session
from app.modules.customer_projects.schemas import (
    ClientKey,
    ProjectCreate,
    ProjectDetail,
    ProjectKind,
    ProjectPage,
    ProjectSummary,
    ProjectUpdate,
)
from app.modules.customer_projects.service import (
    ProjectConflictError,
    ProjectGoneError,
    ProjectMediaError,
    ProjectNotFoundError,
    ProjectService,
)

router = APIRouter(prefix="/api/profile/projects", tags=["customer-projects"])


def get_project_service(request: Request) -> ProjectService:
    return ProjectService(request.app.state.settings)


Service = Annotated[ProjectService, Depends(get_project_service)]


def project_error(error: Exception) -> HTTPException:
    status, detail = {
        ProjectNotFoundError: (404, "Project or product not found"),
        ProjectConflictError: (409, "Project version or creation key conflict"),
        ProjectGoneError: (410, "Project was deleted"),
        ProjectMediaError: (422, "Project media is unavailable"),
        IntegrityError: (409, "Project write conflict"),
    }[type(error)]
    return HTTPException(status_code=status, detail=detail, headers={"Cache-Control": "no-store"})


@router.post("", response_model=ProjectDetail, response_model_exclude_unset=True, status_code=201)
async def create_project(
    payload: ProjectCreate,
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
) -> ProjectDetail:
    try:
        result, created = await service.create(session, user_id=user.id, payload=payload)
        await session.commit()
    except (
        ProjectNotFoundError,
        ProjectConflictError,
        ProjectGoneError,
        ProjectMediaError,
        IntegrityError,
    ) as error:
        await session.rollback()
        raise project_error(error) from error
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("", response_model=ProjectPage)
async def list_projects(
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
    kind: Annotated[ProjectKind, Query()] = "draft",
    limit: Annotated[int, Query(ge=1, le=50)] = 24,
    cursor: Annotated[int | None, Query(gt=0, le=2_147_483_647)] = None,
) -> ProjectPage:
    response.headers["Cache-Control"] = "no-store"
    return await service.list_page(session, user_id=user.id, kind=kind, limit=limit, cursor=cursor)


@router.get("/by-client-key/{client_key}", response_model=ProjectSummary)
async def get_creation_receipt(
    client_key: ClientKey,
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
) -> ProjectSummary:
    try:
        result = await service.creation_receipt(session, user_id=user.id, client_key=client_key)
    except (ProjectNotFoundError, ProjectGoneError) as error:
        raise project_error(error) from error
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{project_id}", response_model=ProjectDetail, response_model_exclude_unset=True)
async def get_project(
    project_id: ResourceId,
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
) -> ProjectDetail:
    try:
        result = await service.get(session, user_id=user.id, project_id=project_id)
    except ProjectNotFoundError as error:
        raise project_error(error) from error
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/{project_id}", response_model=ProjectDetail, response_model_exclude_unset=True)
async def update_project(
    project_id: ResourceId,
    payload: ProjectUpdate,
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
) -> ProjectDetail:
    try:
        result = await service.update(
            session, user_id=user.id, project_id=project_id, payload=payload
        )
        await session.commit()
    except (ProjectNotFoundError, ProjectConflictError, ProjectMediaError, IntegrityError) as error:
        await session.rollback()
        raise project_error(error) from error
    response.headers["Cache-Control"] = "no-store"
    return result


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: ResourceId,
    session: Session,
    user: CurrentUser,
    service: Service,
    expected_version: Annotated[int, Query(gt=0, le=2_147_483_646)],
) -> Response:
    try:
        await service.remove(
            session, user_id=user.id, project_id=project_id, expected_version=expected_version
        )
        await session.commit()
    except (ProjectNotFoundError, ProjectConflictError, IntegrityError) as error:
        await session.rollback()
        raise project_error(error) from error
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
