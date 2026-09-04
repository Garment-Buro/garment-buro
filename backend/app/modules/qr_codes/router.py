from __future__ import annotations

from typing import Annotated

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.modules.qr_codes.schemas import MAX_QR_PATH_BYTES, MAX_QR_SIZE, QrCodeSurface
from app.modules.qr_codes.service import QrCodeService, QrCodeValidationError

router = APIRouter(prefix="/api/qr-code", tags=["qr-codes"])


def get_qr_code_service(request: Request) -> QrCodeService:
    service = request.app.state.qr_code_service
    if not isinstance(service, QrCodeService):
        raise RuntimeError("QR code service is not initialized")
    return service


@router.get(
    "",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}}, "description": "Generated QR code"},
        422: {"description": "Unsafe or invalid target path"},
    },
)
async def generate_page_qr_code(
    path: Annotated[
        str,
        Query(min_length=1, max_length=MAX_QR_PATH_BYTES, description="Root-relative page path"),
    ],
    service: Annotated[QrCodeService, Depends(get_qr_code_service)],
    surface: Annotated[QrCodeSurface, Query(description="Trusted Garment Buro web surface")] = (
        QrCodeSurface.SITE
    ),
    size: Annotated[int, Query(ge=128, le=MAX_QR_SIZE)] = 512,
) -> Response:
    try:
        artifact = await to_thread.run_sync(service.generate_png, path, surface, size)
    except QrCodeValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_qr_target", "message": str(error)},
            headers={"Cache-Control": "no-store"},
        ) from error

    return Response(
        artifact.content,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": 'inline; filename="garment-buro-qr.png"',
            "ETag": f'"{artifact.etag}"',
            "X-QR-Target": service.header_safe_target(artifact.target_url),
        },
    )
