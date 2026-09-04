from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.checkout.schemas import CheckoutResponse
from app.modules.checkout.service import (
    CheckoutActorError,
    CheckoutDisabledError,
    CheckoutPaymentError,
    CheckoutPaymentMethodError,
    CheckoutReceiptError,
    CheckoutService,
)
from app.modules.identity.exceptions import InvalidEmailError
from app.modules.identity.models import User
from app.modules.identity.router import get_optional_current_identity_user
from app.modules.inventory.service import InsufficientStockError
from app.modules.orders.schemas import MAX_ORDER_PAYLOAD_BYTES, OrderCreationCommand
from app.modules.orders.security import (
    InvalidOrderGuestAccessTokenError,
    InvalidOrderIdempotencyKeyError,
    normalize_order_idempotency_key,
)
from app.modules.orders.service import (
    OrderCatalogItemError,
    OrderGuestAccessStateError,
    OrderIdempotencyConflictError,
    OrderTotalMismatchError,
)
from app.modules.payments.creation import (
    PaymentCreationDisabledError,
    PaymentCreationInProgressError,
    PaymentCreationRequestConflictError,
    PaymentCreationRetryExpiredError,
)
from app.modules.payments.service import (
    PaymentAttemptInProgressError,
    PaymentIdempotencyConflictError,
    PaymentStateError,
)

router = APIRouter(prefix="/api/orders", tags=["checkout"])


def get_checkout_service(request: Request) -> CheckoutService:
    service = request.app.state.checkout_service
    if not isinstance(service, CheckoutService):
        raise RuntimeError("Checkout service is not initialized")
    return service


@router.post(
    "",
    response_model=CheckoutResponse,
    responses={
        400: {"description": "Invalid checkout actor or header"},
        401: {"description": "Invalid access token"},
        409: {"description": "Checkout state conflict"},
        413: {"description": "Checkout body is too large"},
        415: {"description": "Unsupported media type"},
        422: {"description": "Invalid checkout command or total"},
        502: {"description": "Payment provider rejected the request"},
        503: {"description": "Checkout outcome is pending or unavailable"},
    },
    openapi_extra={
        "parameters": [
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": True,
                "schema": {
                    "type": "string",
                    "minLength": 16,
                    "maxLength": 128,
                    "pattern": "^[A-Za-z0-9_-]{16,128}$",
                },
            }
        ],
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OrderCreationCommand.model_json_schema(),
                }
            },
        },
    },
)
async def create_checkout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
    user: Annotated[User | None, Depends(get_optional_current_identity_user)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", include_in_schema=False),
    ] = None,
    guest_access_token: Annotated[
        str | None,
        Header(alias="X-Order-Access-Token"),
    ] = None,
) -> CheckoutResponse:
    _require_json_content_type(request)
    body = await _read_limited_body(request)
    command = _parse_command(body)
    try:
        normalized_key = normalize_order_idempotency_key(idempotency_key or "")
        result = await service.checkout(
            session,
            idempotency_key=normalized_key,
            command=command,
            user_id=user.id if user is not None else None,
            guest_access_token=guest_access_token,
            partner_attribution_token=request.cookies.get(
                request.app.state.settings.partner_attribution_cookie_name
            ),
        )
    except (
        CheckoutActorError,
        CheckoutPaymentMethodError,
        InvalidOrderGuestAccessTokenError,
        InvalidOrderIdempotencyKeyError,
        OrderGuestAccessStateError,
    ) as error:
        raise _error(400, "Invalid checkout request") from error
    except (InvalidEmailError, OrderTotalMismatchError, CheckoutReceiptError) as error:
        raise _error(422, "Invalid checkout total or receipt") from error
    except (
        InsufficientStockError,
        OrderCatalogItemError,
        OrderIdempotencyConflictError,
        PaymentAttemptInProgressError,
        PaymentIdempotencyConflictError,
        PaymentStateError,
    ) as error:
        raise _error(409, "Checkout state conflict") from error
    except PaymentCreationInProgressError as error:
        raise _error(409, "Payment creation is already in progress", retry_after=2) from error
    except PaymentCreationRetryExpiredError as error:
        raise _error(409, "Payment creation retry window expired") from error
    except PaymentCreationRequestConflictError as error:
        raise _error(409, "Payment request state conflict") from error
    except PaymentCreationDisabledError as error:
        raise _error(503, "Checkout is unavailable") from error
    except CheckoutDisabledError as error:
        raise _error(503, "Checkout is unavailable") from error
    except CheckoutPaymentError as error:
        if error.outcome_unknown:
            raise _error(
                503,
                {"code": "payment_outcome_unknown", "order_id": error.order_id},
                retry_after=2,
            ) from error
        raise _error(
            502,
            {"code": "payment_rejected", "order_id": error.order_id},
        ) from error
    except SQLAlchemyError as error:
        raise _error(503, "Checkout storage is unavailable", retry_after=2) from error
    except Exception as error:  # noqa: BLE001 - keep the public checkout failure contract safe
        raise _error(503, "Checkout is unavailable", retry_after=2) from error

    response.headers["Cache-Control"] = "no-store"
    return CheckoutResponse(order_id=result.order_id, payment_url=result.payment_url)


def _require_json_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type != "application/json":
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
        if length > MAX_ORDER_PAYLOAD_BYTES:
            raise _error(status.HTTP_413_CONTENT_TOO_LARGE, "Checkout body is too large")

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_ORDER_PAYLOAD_BYTES:
            raise _error(status.HTTP_413_CONTENT_TOO_LARGE, "Checkout body is too large")
        body.extend(chunk)
    if not body:
        raise _error(422, "Invalid checkout command")
    return bytes(body)


def _parse_command(body: bytes) -> OrderCreationCommand:
    try:
        return OrderCreationCommand.model_validate_json(body)
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
