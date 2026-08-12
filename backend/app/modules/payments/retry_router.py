from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.checkout.schemas import CheckoutResponse
from app.modules.identity.models import User
from app.modules.identity.router import get_optional_current_identity_user
from app.modules.payments.creation import (
    PaymentCreationDisabledError,
    PaymentCreationInProgressError,
    PaymentCreationRequestConflictError,
    PaymentCreationRetryExpiredError,
)
from app.modules.payments.retry import (
    PaymentRetryActorError,
    PaymentRetryDisabledError,
    PaymentRetryError,
    PaymentRetryNotFoundError,
    PaymentRetryService,
    PaymentRetryStateError,
)
from app.modules.payments.security import InvalidPaymentAttemptKeyError
from app.modules.payments.service import (
    PaymentAttemptInProgressError,
    PaymentIdempotencyConflictError,
    PaymentStateError,
)

router = APIRouter(prefix="/api/orders", tags=["payments"])


def get_payment_retry_service(request: Request) -> PaymentRetryService:
    service = request.app.state.payment_retry_service
    if not isinstance(service, PaymentRetryService):
        raise RuntimeError("Payment retry service is not initialized")
    return service


@router.post(
    "/{order_id}/payment-attempts",
    response_model=CheckoutResponse,
    responses={
        400: {"description": "Invalid payment retry request"},
        401: {"description": "Invalid access token"},
        404: {"description": "Owned target order was not found"},
        409: {"description": "Payment retry state conflict"},
        502: {"description": "Payment provider rejected the request"},
        503: {"description": "Payment outcome is pending or unavailable"},
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
        ]
    },
)
async def retry_order_payment(
    order_id: str,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PaymentRetryService, Depends(get_payment_retry_service)],
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
    await _require_empty_body(request)
    parsed_order_id = _parse_order_id(order_id)
    try:
        result = await service.retry(
            session,
            order_id=parsed_order_id,
            idempotency_key=idempotency_key or "",
            user_id=user.id if user is not None else None,
            guest_access_token=guest_access_token,
        )
    except (PaymentRetryActorError, InvalidPaymentAttemptKeyError) as error:
        raise _error(400, "Invalid payment retry request") from error
    except PaymentRetryNotFoundError as error:
        raise _error(404, "Order not found") from error
    except (
        PaymentAttemptInProgressError,
        PaymentIdempotencyConflictError,
        PaymentRetryStateError,
        PaymentStateError,
    ) as error:
        raise _error(409, "Payment retry state conflict") from error
    except PaymentCreationInProgressError as error:
        raise _error(409, "Payment creation is already in progress", retry_after=2) from error
    except PaymentCreationRetryExpiredError as error:
        raise _error(409, "Payment creation retry window expired") from error
    except PaymentCreationRequestConflictError as error:
        raise _error(409, "Payment request state conflict") from error
    except (PaymentCreationDisabledError, PaymentRetryDisabledError) as error:
        raise _error(503, "Payment retry is unavailable") from error
    except PaymentRetryError as error:
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
        raise _error(503, "Payment storage is unavailable", retry_after=2) from error
    except Exception as error:  # noqa: BLE001 - keep the public retry failure contract safe
        raise _error(503, "Payment retry is unavailable", retry_after=2) from error

    response.headers["Cache-Control"] = "no-store"
    return CheckoutResponse(order_id=result.order_id, payment_url=result.payment_url)


async def _require_empty_body(request: Request) -> None:
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            length = int(declared_length)
        except ValueError as error:
            raise _error(400, "Invalid Content-Length") from error
        if length < 0:
            raise _error(400, "Invalid Content-Length")
        if length > 0:
            raise _error(400, "Payment retry body must be empty")
    async for chunk in request.stream():
        if chunk:
            raise _error(400, "Payment retry body must be empty")


def _parse_order_id(value: str) -> int:
    try:
        order_id = int(value)
    except ValueError as error:
        raise _error(404, "Order not found") from error
    if order_id <= 0 or str(order_id) != value:
        raise _error(404, "Order not found")
    return order_id


def _error(
    status_code: int,
    detail: str | dict[str, object],
    *,
    retry_after: int | None = None,
) -> HTTPException:
    headers = {"Cache-Control": "no-store"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return HTTPException(status_code=status_code, detail=detail, headers=headers)
