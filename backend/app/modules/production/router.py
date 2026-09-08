from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.crm.command_security import normalize_crm_idempotency_key
from app.modules.crm.file_models import CrmFileAttachment, CrmFileRole
from app.modules.crm.file_service import (
    CrmFileConflictError,
    CrmFileNotFoundError,
    CrmFileService,
    CrmFileStorageError,
    UnsupportedCrmFileError,
)
from app.modules.crm.models import CrmProductionUnit
from app.modules.crm.production_service import (
    CrmProductionConflictError,
    CrmProductionVersionConflictError,
)
from app.modules.crm.service import CrmProjectStateError, CrmProjectVersionConflictError
from app.modules.identity.models import User
from app.modules.production.admin_router import router as admin_router
from app.modules.production.auth_router import get_production_user
from app.modules.production.auth_router import router as auth_router
from app.modules.production.evidence import ProductionConflict, ProductionNotFound
from app.modules.production.models import ProductionSpecificationFile
from app.modules.production.read_service import ProductionReadService
from app.modules.production.schemas import CommandReceipt, ProductionCommand
from app.modules.production.security import ProductionDenied, can_administer, stations_for_user
from app.modules.production.service import ProductionService

router = APIRouter(prefix="/api/production", tags=["production-terminal"])
router.include_router(auth_router, prefix="")
router.include_router(admin_router)
Session = Annotated[AsyncSession, Depends(get_database_session)]
CurrentUser = Annotated[User, Depends(get_production_user)]


async def access(request: Request, response: Response, user: CurrentUser, session: Session):
    response.headers["Cache-Control"] = "no-store"
    if not request.app.state.settings.production_terminal_enabled:
        raise HTTPException(503, "Производственный терминал пока выключен")
    try:
        return user, await stations_for_user(session, user.id)
    except ProductionDenied as error:
        raise HTTPException(403, str(error)) from error


Auth = Annotated[tuple[User, list[str]], Depends(access)]


@router.get("/me")
async def me(auth: Auth, request: Request, session: Session):
    user, stations = auth
    return {
        "id": user.id,
        "name": user.first_name or user.email or "Сотрудник",
        "stations": stations,
        "can_administer": getattr(request.state, "production_station", None) == "admin"
        and await can_administer(session, user.id),
    }


@router.get("/projects")
async def projects(
    _auth: Auth,
    session: Session,
    cursor: int | None = Query(default=None, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
):
    return await ProductionReadService().queue(session, cursor=cursor, limit=limit)


@router.get("/projects/{project_id}")
async def project(project_id: int, auth: Auth, session: Session):
    try:
        return await ProductionReadService().detail(
            session, project_id=project_id, stations=auth[1]
        )
    except ProductionNotFound as error:
        raise HTTPException(404, str(error)) from error
    except ProductionConflict as error:
        raise HTTPException(409, str(error)) from error


@router.post("/projects/{project_id}/commands", response_model=CommandReceipt)
async def command(
    project_id: int,
    payload: ProductionCommand,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    auth: Auth,
    session: Session,
):
    try:
        key = normalize_crm_idempotency_key(idempotency_key)
        return await ProductionService(request.app.state.settings).execute(
            session, project_id=project_id, actor_id=auth[0].id, key=key, command=payload
        )
    except ProductionDenied as error:
        raise HTTPException(403, str(error)) from error
    except ProductionNotFound as error:
        raise HTTPException(404, str(error)) from error
    except (
        ProductionConflict,
        CrmProductionConflictError,
        CrmProductionVersionConflictError,
        CrmProjectStateError,
        CrmProjectVersionConflictError,
        IntegrityError,
    ) as error:
        await session.rollback()
        raise HTTPException(
            409,
            str(error)
            if not isinstance(error, IntegrityError)
            else "Конфликт записи. Обновите экран",
        ) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


def file_service(request):
    service = request.app.state.crm_file_service
    if not isinstance(service, CrmFileService):
        raise HTTPException(503, "Приватное хранилище файлов не подключено")
    return service


@router.post("/units/{unit_id}/files")
async def upload(
    unit_id: int,
    file: UploadFile,
    request: Request,
    auth: Auth,
    session: Session,
    slot: int = Query(ge=0),
):
    if "tech" not in auth[1]:
        raise HTTPException(403, "Файлы закрепляет технолог")
    unit = await session.get(CrmProductionUnit, unit_id)
    if unit is None:
        raise HTTPException(404, "Вещь не найдена")
    limit = request.app.state.settings.crm_file_max_upload_bytes
    try:
        data = await file.read(limit + 1)
    finally:
        await file.close()
    if len(data) > limit:
        raise HTTPException(413, "Файл превышает допустимый размер")
    try:
        return await file_service(request).upload(
            session,
            data=data,
            original_filename=file.filename or "upload",
            role=CrmFileRole.PRODUCTION_EVIDENCE,
            production_unit_id=unit_id,
            sort_order=slot,
            actor_user_id=auth[0].id,
        )
    except (UnsupportedCrmFileError, ValueError) as error:
        raise HTTPException(400, str(error)) from error
    except CrmFileConflictError as error:
        raise HTTPException(409, str(error)) from error
    except CrmFileStorageError as error:
        raise HTTPException(503, str(error)) from error


@router.get("/files/{attachment_id}/download")
async def download(attachment_id: int, request: Request, auth: Auth, session: Session):
    attachment = await session.get(CrmFileAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(404, "Файл не найден")
    if not set(auth[1]) & {"tech", "cut", "dtf", "application"}:
        raise HTTPException(403, "Файлы доступны участкам раскроя и печати")
    if "tech" in auth[1]:
        if attachment.production_unit_id is None and attachment.tech_card_revision_id is None:
            raise HTTPException(404, "Файл не относится к производственной вещи")
    else:
        roles = []
        if "cut" in auth[1]:
            roles.append("pattern")
        if set(auth[1]) & {"dtf", "application"}:
            roles.append("print")
        if not await session.scalar(
            select(ProductionSpecificationFile.id).where(
                ProductionSpecificationFile.attachment_id == attachment_id,
                ProductionSpecificationFile.role.in_(roles),
            )
        ):
            raise HTTPException(403, "Файл не закреплён для вашего участка")
    try:
        return await file_service(request).get_download(
            session, attachment_id=attachment_id, actor_user_id=auth[0].id
        )
    except CrmFileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except CrmFileStorageError as error:
        raise HTTPException(503, str(error)) from error
