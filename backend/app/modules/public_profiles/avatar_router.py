from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
)
from minio.error import S3Error
from sqlalchemy.exc import SQLAlchemyError
from urllib3.exceptions import HTTPError

from app.integrations.minio import MinioStorage
from app.modules.media.errors import PrivateStorageUnavailableError, UnsupportedMediaError
from app.modules.public_profiles.avatar_service import AvatarService, AvatarTooLargeError
from app.modules.public_profiles.router import CurrentUser, Session
from app.modules.public_profiles.router import Service as ProfileService
from app.modules.public_profiles.schemas import OwnPublicProfileResponse, ProfileSlug
from app.modules.public_profiles.service import ProfileConflictError, ProfileUnavailableError

router = APIRouter(tags=["public-profiles"])
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
ResourceId = Annotated[int, Path(gt=0, le=2_147_483_647)]
ExpectedVersion = Annotated[int, Query(ge=1, le=2_147_483_646)]


def get_avatar_service(request: Request) -> AvatarService:
    storage = getattr(request.app.state, "storage", None)
    if not isinstance(storage, MinioStorage) or not storage.enabled:
        raise HTTPException(status_code=503, detail="Avatar storage unavailable", headers=NO_STORE)
    return AvatarService(storage)


Service = Annotated[AvatarService, Depends(get_avatar_service)]


@asynccontextmanager
async def avatar_errors(session):
    try:
        yield
    except ProfileConflictError as error:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Public profile changed", headers=NO_STORE
        ) from error
    except ProfileUnavailableError as error:
        await session.rollback()
        raise HTTPException(
            status_code=404, detail="Avatar unavailable", headers=NO_STORE
        ) from error
    except UnsupportedMediaError as error:
        raise HTTPException(status_code=415, detail=str(error), headers=NO_STORE) from error
    except AvatarTooLargeError as error:
        raise HTTPException(
            status_code=413, detail="Avatar exceeds upload limit", headers=NO_STORE
        ) from error
    except (
        S3Error,
        HTTPError,
        OSError,
        SQLAlchemyError,
        PrivateStorageUnavailableError,
        ValueError,
    ) as error:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Avatar storage unavailable", headers=NO_STORE
        ) from error


@router.post("/api/profile/public/avatar", response_model=OwnPublicProfileResponse, status_code=201)
async def upload_avatar(
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
    expected_version: ExpectedVersion,
    file: Annotated[UploadFile, File()],
):
    try:
        async with avatar_errors(session):
            result = await service.upload(
                session,
                user_id=user.id,
                expected_version=expected_version,
                data=await file.read(service.max_upload_bytes + 1),
                original_filename=file.filename or "avatar",
            )
    finally:
        await file.close()
    response.headers.update(NO_STORE)
    return result


@router.delete("/api/profile/public/avatar", response_model=OwnPublicProfileResponse)
async def remove_avatar(
    response: Response,
    session: Session,
    user: CurrentUser,
    service: ProfileService,
    expected_version: ExpectedVersion,
):
    async with avatar_errors(session):
        result = await service.remove_avatar(session, user.id, expected_version)
        await session.commit()
    response.headers.update(NO_STORE)
    return result


@router.get("/api/profile/public/avatar/{media_id}")
async def read_own_avatar(
    media_id: ResourceId, session: Session, user: CurrentUser, service: Service
):
    async with avatar_errors(session):
        data = await service.read(session, user_id=user.id, media_id=media_id)
    return Response(data, media_type="image/webp", headers=NO_STORE)


@router.get("/api/people/{slug}/avatar/{media_id}")
async def read_public_avatar(
    slug: ProfileSlug, media_id: ResourceId, session: Session, service: Service
):
    async with avatar_errors(session):
        data = await service.read(session, slug=slug, media_id=media_id)
    return Response(data, media_type="image/webp", headers=NO_STORE)


@router.get("/api/people/{slug}/avatar/{media_id}/preview")
async def read_public_avatar_card(
    slug: ProfileSlug, media_id: ResourceId, session: Session, service: Service
):
    async with avatar_errors(session):
        data = await service.read(session, slug=slug, media_id=media_id, card_preview=True)
    return Response(data, media_type="image/webp", headers=NO_STORE)
