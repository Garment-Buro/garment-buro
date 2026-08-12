from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.delivery.provider import CdekProviderError
from app.modules.delivery.quote_schemas import (
    MAX_CDEK_QUOTE_PAYLOAD_BYTES,
    CdekQuoteRequest,
    CdekQuoteResponse,
)
from app.modules.delivery.quote_service import CdekQuoteService, CdekQuoteValidationError

router = APIRouter(prefix="/api/cdek", tags=["delivery"])


def get_cdek_quote_service(request: Request) -> CdekQuoteService:
    service = request.app.state.cdek_quote_service
    if not isinstance(service, CdekQuoteService):
        raise RuntimeError("CDEK quote service is not initialized")
    return service


@router.post(
    "/calculate",
    response_model=CdekQuoteResponse,
    responses={
        409: {"description": "Catalog logistics state conflict"},
        413: {"description": "Quote body is too large"},
        415: {"description": "Unsupported media type"},
        422: {"description": "Invalid quote or provider rejected the request"},
        503: {"description": "Quote storage or provider unavailable"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": CdekQuoteRequest.model_json_schema()}},
        }
    },
)
async def calculate_cdek_quote(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CdekQuoteService, Depends(get_cdek_quote_service)],
) -> CdekQuoteResponse:
    _require_json_content_type(request)
    command = _parse_command(await _read_limited_body(request))
    try:
        prepared = await service.prepare(session, command)
        # Release the implicit read transaction before external provider I/O.
        await session.rollback()
        quote = await service.calculate(prepared)
    except CdekQuoteValidationError as error:
        if error.code in {"cdek_product_unavailable", "cdek_logistics_missing"}:
            raise _error(409, {"code": error.code}) from error
        raise _error(422, {"code": error.code}) from error
    except CdekProviderError as error:
        if error.rejected:
            raise _error(422, {"code": "cdek_quote_rejected"}) from error
        raise _error(
            503,
            {"code": "cdek_quote_unavailable"},
            retry_after=2 if error.retryable else None,
        ) from error
    except SQLAlchemyError as error:
        raise _error(503, {"code": "cdek_quote_storage_unavailable"}, retry_after=2) from error
    except Exception as error:  # noqa: BLE001 - keep public provider failures opaque
        raise _error(503, {"code": "cdek_quote_unavailable"}, retry_after=2) from error

    response.headers["Cache-Control"] = "no-store"
    return CdekQuoteResponse(
        delivery_price=float(quote.delivery_sum),
        period_min=quote.period_min,
        period_max=quote.period_max,
        tariff_code=prepared.tariff_code,
    )


def _require_json_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    if content_type.partition(";")[0].strip().lower() != "application/json":
        raise _error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported media type")


async def _read_limited_body(request: Request) -> bytes:
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            length = int(declared_length)
        except ValueError as error:
            raise _error(400, "Invalid Content-Length") from error
        if length < 0:
            raise _error(400, "Invalid Content-Length")
        if length > MAX_CDEK_QUOTE_PAYLOAD_BYTES:
            raise _error(status.HTTP_413_CONTENT_TOO_LARGE, "Quote body is too large")

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_CDEK_QUOTE_PAYLOAD_BYTES:
            raise _error(status.HTTP_413_CONTENT_TOO_LARGE, "Quote body is too large")
        body.extend(chunk)
    if not body:
        raise _error(422, "Invalid CDEK quote")
    return bytes(body)


def _parse_command(body: bytes) -> CdekQuoteRequest:
    try:
        return CdekQuoteRequest.model_validate_json(body)
    except ValidationError as error:
        detail = [
            {
                "type": item["type"],
                "loc": ["body", *item.get("loc", ())],
                "msg": item["msg"],
            }
            for item in error.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise _error(422, detail) from error


def _error(
    status_code: int,
    detail: str | dict[str, object] | list[dict[str, object]],
    *,
    retry_after: int | None = None,
) -> HTTPException:
    headers = {"Cache-Control": "no-store"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return HTTPException(status_code=status_code, detail=detail, headers=headers)
