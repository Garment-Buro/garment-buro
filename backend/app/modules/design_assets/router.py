from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from minio.error import S3Error
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from urllib3.exceptions import HTTPError

from app.db.session import get_database_session
from app.integrations.minio import MinioStorage
from app.modules.design_assets.schemas import DesignImage, DesignImageImport, ImportedDesignImages
from app.modules.design_assets.security import DesignAssetUnavailableError
from app.modules.design_assets.service import DesignImageTooLargeError, DesignMediaService
from app.modules.identity.models import User
from app.modules.identity.router import get_current_identity_user
from app.modules.media.errors import PrivateStorageUnavailableError, UnsupportedMediaError

router = APIRouter(prefix="/api/design-media", tags=["design-media"])
owner_router = APIRouter(prefix="/api/design-media", tags=["design-media"])
NO_STORE = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def get_design_media_service(request: Request) -> DesignMediaService:
    storage = getattr(request.app.state, "storage", None)
    if not isinstance(storage, MinioStorage) or not storage.enabled:
        raise HTTPException(status_code=503, detail="Design storage unavailable", headers=NO_STORE)
    return DesignMediaService(storage)


Service = Annotated[DesignMediaService, Depends(get_design_media_service)]
Session = Annotated[AsyncSession, Depends(get_database_session)]
CurrentUser = Annotated[User, Depends(get_current_identity_user)]


@asynccontextmanager
async def design_errors(session):
    try:
        yield
    except DesignAssetUnavailableError as error:
        await session.rollback()
        raise HTTPException(
            status_code=404, detail="Design image unavailable", headers=NO_STORE
        ) from error
    except UnsupportedMediaError as error:
        raise HTTPException(
            status_code=415, detail="Unsupported design image", headers=NO_STORE
        ) from error
    except DesignImageTooLargeError as error:
        raise HTTPException(
            status_code=413, detail="Design image exceeds upload limit", headers=NO_STORE
        ) from error
    except (S3Error, HTTPError, OSError, SQLAlchemyError, PrivateStorageUnavailableError) as error:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Design storage unavailable", headers=NO_STORE
        ) from error


@router.post("", response_model=DesignImage, status_code=201)
async def upload_design_image(
    request: Request, response: Response, session: Session, service: Service
):
    # A raw bounded stream avoids spooling an unlimited multipart upload before validation.
    async with design_errors(session):
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > service.max_upload_bytes:
                raise DesignImageTooLargeError
            data.extend(chunk)
        result = await service.upload(session, data=bytes(data), now=datetime.now(timezone.utc))
    response.headers.update(NO_STORE)
    return result


@owner_router.post("/import", response_model=ImportedDesignImages, status_code=201)
async def import_design_images(
    payload: DesignImageImport,
    response: Response,
    session: Session,
    user: CurrentUser,
    service: Service,
):
    async with design_errors(session):
        result = await service.import_owned(
            session, user_id=user.id, media_ids=payload.media_ids, now=datetime.now(timezone.utc)
        )
    response.headers.update(NO_STORE)
    return result


@router.get("/{token}/content")
async def read_design_image(token: str, session: Session, service: Service):
    async with design_errors(session):
        data, mime = await service.read(session, token=token, now=datetime.now(timezone.utc))
    return Response(data, media_type=mime, headers=NO_STORE)
