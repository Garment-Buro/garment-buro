from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.crm.dependencies import require_crm_reader
from app.modules.crm.file_models import CrmFileRole
from app.modules.crm.file_schemas import CrmFileDownloadReceipt, CrmFileUploadReceipt
from app.modules.crm.file_service import (
    CrmFileConflictError,
    CrmFileNotFoundError,
    CrmFileService,
    CrmFileStorageError,
    UnsupportedCrmFileError,
)
from app.modules.identity.models import User

router = APIRouter(prefix="/api/crm/files", tags=["crm-staff-files"])


def get_crm_file_service(request: Request) -> CrmFileService:
    service = request.app.state.crm_file_service
    if not isinstance(service, CrmFileService):
        raise RuntimeError("CRM file service is not initialized")
    return service


@router.post("", response_model=CrmFileUploadReceipt, status_code=201)
async def upload_crm_file(
    request: Request,
    response: Response,
    file: Annotated[UploadFile, File()],
    role: Annotated[CrmFileRole, Form()],
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmFileService, Depends(get_crm_file_service)],
    tech_card_revision_id: Annotated[int | None, Form(gt=0)] = None,
    production_project_id: Annotated[int | None, Form(gt=0)] = None,
    production_unit_id: Annotated[int | None, Form(gt=0)] = None,
    sort_order: Annotated[int, Form(ge=0)] = 0,
) -> CrmFileUploadReceipt:
    _no_store(response)
    limit = request.app.state.settings.crm_file_max_upload_bytes
    try:
        data = await file.read(limit + 1)
    finally:
        await file.close()
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="Uploaded CRM file is too large")
    try:
        result = await service.upload(
            session,
            data=data,
            original_filename=file.filename or "upload",
            role=role,
            tech_card_revision_id=tech_card_revision_id,
            production_project_id=production_project_id,
            production_unit_id=production_unit_id,
            sort_order=sort_order,
            actor_user_id=actor.id,
        )
    except CrmFileNotFoundError as error:
        raise HTTPException(status_code=404, detail="CRM file target not found") from error
    except UnsupportedCrmFileError as error:
        raise HTTPException(status_code=415, detail="Unsupported CRM file type") from error
    except CrmFileConflictError as error:
        raise HTTPException(status_code=409, detail="CRM file slot conflict") from error
    except CrmFileStorageError as error:
        raise HTTPException(status_code=503, detail="Private CRM storage is unavailable") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid CRM file metadata") from error
    return CrmFileUploadReceipt(
        attachment_id=result.attachment_id,
        media_id=result.media_id,
        content_type=result.content_type,
        size_bytes=result.size_bytes,
        checksum_sha256=result.checksum_sha256,
    )


@router.get("/{attachment_id}/download", response_model=CrmFileDownloadReceipt)
async def get_crm_file_download(
    attachment_id: Annotated[int, Path(gt=0)],
    response: Response,
    actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmFileService, Depends(get_crm_file_service)],
) -> CrmFileDownloadReceipt:
    _no_store(response)
    try:
        result = await service.get_download(
            session,
            attachment_id=attachment_id,
            actor_user_id=actor.id,
        )
    except CrmFileNotFoundError as error:
        raise HTTPException(status_code=404, detail="CRM file not found") from error
    except CrmFileStorageError as error:
        raise HTTPException(status_code=503, detail="Private CRM storage is unavailable") from error
    return CrmFileDownloadReceipt(
        attachment_id=result.attachment_id,
        filename=result.filename,
        content_type=result.content_type,
        size_bytes=result.size_bytes,
        checksum_sha256=result.checksum_sha256,
        expires_seconds=result.expires_seconds,
        url=result.url,
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
