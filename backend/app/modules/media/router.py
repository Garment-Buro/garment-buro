from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.integrations.minio import MinioStorage, get_minio_storage
from app.modules.catalog.dependencies import require_catalog_writer
from app.modules.identity.models import User
from app.modules.media.service import MediaService, UnsupportedMediaError

router = APIRouter(tags=["media"])
write_router = APIRouter(tags=["catalog-admin"])


def get_media_service(request: Request) -> MediaService:
    return MediaService(request.app.state.storage)


@router.get("/uploads/{filename}", include_in_schema=False)
async def redirect_legacy_upload(
    filename: str,
    storage: Annotated[MinioStorage, Depends(get_minio_storage)],
) -> RedirectResponse:
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        target_url = storage.public_url(f"uploads/{filename}")
    except ValueError as error:
        raise HTTPException(status_code=404, detail="File not found") from error
    return RedirectResponse(
        url=target_url,
        status_code=307,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@write_router.post("/api/upload")
async def upload_catalog_media(
    request: Request,
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[MediaService, Depends(get_media_service)],
) -> dict[str, str]:
    limit = request.app.state.settings.media_max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="Uploaded media is too large")
    try:
        uploaded = await service.upload_catalog_media(
            session,
            data=data,
            original_filename=file.filename or "upload",
            actor_user_id=user.id,
        )
    except UnsupportedMediaError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    return {"url": uploaded.public_url}
