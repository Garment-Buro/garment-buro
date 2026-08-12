from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_database_session
from app.modules.payments.security import (
    InvalidPaymentWebhookSourceError,
    resolve_payment_webhook_source_ip,
)
from app.modules.payments.service import (
    MAX_PAYMENT_WEBHOOK_BYTES,
    InvalidPaymentWebhookError,
    PaymentEventConflictError,
    PaymentService,
    UntrustedPaymentWebhookError,
)

router = APIRouter(tags=["payments"])


class PaymentWebhookAcknowledgement(BaseModel):
    status: Literal["ok"] = "ok"


def get_payment_service(request: Request) -> PaymentService:
    service = request.app.state.payment_service
    if not isinstance(service, PaymentService):
        raise RuntimeError("Payment service is not initialized")
    return service


@router.post(
    "/api/webhooks/yookassa",
    response_model=PaymentWebhookAcknowledgement,
    responses={
        400: {"description": "Invalid notification"},
        404: {"description": "Webhook endpoint or source not found"},
        409: {"description": "Conflicting provider evidence"},
        413: {"description": "Notification body is too large"},
        415: {"description": "Unsupported media type"},
        503: {"description": "Durable intake is unavailable"},
    },
)
async def intake_yookassa_webhook(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentWebhookAcknowledgement:
    settings: Settings = request.app.state.settings
    source_ip = _source_ip(request, settings)
    _require_json_content_type(request)
    raw_body = await _read_limited_body(request)
    try:
        await service.intake_event(
            session,
            raw_body=raw_body,
            source_ip=source_ip,
        )
        await session.commit()
    except UntrustedPaymentWebhookError as error:
        await session.rollback()
        raise _not_found() from error
    except InvalidPaymentWebhookError as error:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Invalid notification") from error
    except PaymentEventConflictError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Conflicting notification") from error
    except ValueError as error:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Invalid notification") from error
    except SQLAlchemyError as error:
        await session.rollback()
        raise HTTPException(status_code=503, detail="Notification intake unavailable") from error

    response.headers["Cache-Control"] = "no-store"
    return PaymentWebhookAcknowledgement()


def _source_ip(request: Request, settings: Settings) -> str:
    try:
        source_ip = resolve_payment_webhook_source_ip(
            peer_ip=request.client.host if request.client is not None else None,
            forwarded_for=request.headers.get("x-forwarded-for"),
            trusted_proxy_networks=settings.payment_webhook_trusted_proxy_networks,
        )
    except InvalidPaymentWebhookSourceError as error:
        raise _not_found() from error
    return source_ip


def _require_json_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type != "application/json":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported media type",
        )


async def _read_limited_body(request: Request) -> bytes:
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            length = int(declared_length)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from error
        if length < 0:
            raise HTTPException(status_code=400, detail="Invalid Content-Length")
        if length > MAX_PAYMENT_WEBHOOK_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Notification body is too large",
            )

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_PAYMENT_WEBHOOK_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Notification body is too large",
            )
        body.extend(chunk)
    if not body:
        raise HTTPException(status_code=400, detail="Invalid notification")
    return bytes(body)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Not found")
