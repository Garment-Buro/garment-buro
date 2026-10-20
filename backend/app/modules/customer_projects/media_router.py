from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from minio.error import S3Error
from sqlalchemy.exc import SQLAlchemyError
from urllib3.exceptions import HTTPError

from app.integrations.minio import MinioStorage
from app.modules.customer_projects.dependencies import CurrentUser, ResourceId, Session
from app.modules.customer_projects.media_schemas import (
    ProjectImage,
    ProjectImageAccess,
    ProjectImages,
)
from app.modules.customer_projects.media_service import (
    ProjectMediaService,
)
from app.modules.customer_projects.service import (
    ProjectConflictError,
    ProjectMediaError,
    ProjectNotFoundError,
)
from app.modules.media.errors import PrivateStorageUnavailableError
from app.modules.media.service import UnsupportedMediaError

router = APIRouter(tags=["customer-projects"])
NO_STORE = {"Cache-Control": "no-store"}


def media_error(status: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status, detail=detail, headers=NO_STORE)


def get_project_media_service(request: Request) -> ProjectMediaService:
    storage = getattr(request.app.state, "storage", None)
    if not isinstance(storage, MinioStorage) or not storage.enabled:
        raise media_error(503, "Project storage is unavailable")
    return ProjectMediaService(storage)


Service = Annotated[ProjectMediaService, Depends(get_project_media_service)]


@router.post("/api/profile/project-media", response_model=ProjectImage, status_code=201)
async def upload_project_image(
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
    file: Annotated[UploadFile, File()],
) -> ProjectImage:
    try:
        data = await file.read(service.max_upload_bytes + 1)
        result = await service.upload(
            session, user_id=user.id, data=data, original_filename=file.filename or "image"
        )
    except UnsupportedMediaError as error:
        raise media_error(415, str(error)) from error
    except ValueError as error:
        raise media_error(413, str(error)) from error
    except ProjectNotFoundError as error:
        await session.rollback()
        raise media_error(404, "Project image is unavailable") from error
    except (S3Error, HTTPError, OSError, SQLAlchemyError, PrivateStorageUnavailableError) as error:
        await session.rollback()
        raise media_error(503, "Project storage is unavailable") from error
    finally:
        await file.close()
    response.headers.update(NO_STORE)
    return result


@router.get("/api/profile/project-media/{media_id}/access", response_model=ProjectImageAccess)
async def project_image_access(
    media_id: ResourceId,
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
) -> ProjectImageAccess:
    try:
        result = await service.access(session, user_id=user.id, media_id=media_id)
    except ProjectNotFoundError as error:
        raise media_error(404, "Project image not found") from error
    except (S3Error, HTTPError, OSError, SQLAlchemyError, PrivateStorageUnavailableError) as error:
        raise media_error(503, "Project storage is unavailable") from error
    response.headers.update(NO_STORE)
    return result


@router.get("/api/profile/projects/{project_id}/media", response_model=ProjectImages)
async def project_images(
    project_id: ResourceId,
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
    version: Annotated[int, Query(gt=0, le=2_147_483_647)],
) -> ProjectImages:
    try:
        result = await service.project_images(
            session, user_id=user.id, project_id=project_id, version=version
        )
    except ProjectNotFoundError as error:
        raise media_error(404, "Project not found") from error
    except ProjectConflictError as error:
        raise media_error(409, "Project version changed") from error
    except ProjectMediaError as error:
        raise media_error(422, "Project images are unavailable") from error
    except (S3Error, HTTPError, OSError, SQLAlchemyError, PrivateStorageUnavailableError) as error:
        raise media_error(503, "Project storage is unavailable") from error
    response.headers.update(NO_STORE)
    return result
