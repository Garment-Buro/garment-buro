from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.identity.models import User
from app.modules.payments.dependencies import require_payment_manager
from app.modules.payments.operation_schemas import OrderPaymentResponse, PaymentOperationResponse
from app.modules.payments.operation_service import (
    PaymentOperationConflictError,
    PaymentOperationDisabledError,
    PaymentOperationFailedError,
    PaymentOperationInProgressError,
    PaymentOperationService,
)
from app.modules.payments.security import InvalidPaymentAttemptKeyError
from app.modules.payments.service import PaymentStateError

router = APIRouter(prefix="/api/payments", tags=["payment-management"])


def get_payment_operation_service(request: Request) -> PaymentOperationService:
    service = request.app.state.payment_operation_service
    if not isinstance(service, PaymentOperationService):
        raise RuntimeError("Payment operation service is not initialized")
    return service


@router.get("/orders/{order_id}", response_model=OrderPaymentResponse)
async def get_order_payment(
    order_id: Annotated[int, Path(ge=1)],
    response: Response,
    _actor: Annotated[User, Depends(require_payment_manager)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PaymentOperationService, Depends(get_payment_operation_service)],
) -> OrderPaymentResponse:
    try:
        result = await service.get_order_payment(session, order_id=order_id)
    except PaymentStateError as error:
        raise _error(404, "Order payment not found") from error
    except PaymentOperationDisabledError as error:
        raise _error(503, "Payment management is unavailable") from error
    response.headers["Cache-Control"] = "no-store"
    return OrderPaymentResponse.model_validate(result)


@router.post("/orders/{order_id}/capture", response_model=PaymentOperationResponse)
async def capture_payment(
    order_id: Annotated[int, Path(ge=1)],
    request: Request,
    response: Response,
    actor: Annotated[User, Depends(require_payment_manager)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PaymentOperationService, Depends(get_payment_operation_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> PaymentOperationResponse:
    return await _execute(
        "capture",
        order_id=order_id,
        request=request,
        response=response,
        actor=actor,
        session=session,
        service=service,
        idempotency_key=idempotency_key,
    )


@router.post("/orders/{order_id}/cancel", response_model=PaymentOperationResponse)
async def cancel_payment(
    order_id: Annotated[int, Path(ge=1)],
    request: Request,
    response: Response,
    actor: Annotated[User, Depends(require_payment_manager)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PaymentOperationService, Depends(get_payment_operation_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> PaymentOperationResponse:
    return await _execute(
        "cancel",
        order_id=order_id,
        request=request,
        response=response,
        actor=actor,
        session=session,
        service=service,
        idempotency_key=idempotency_key,
    )


async def _execute(
    operation: Literal["capture", "cancel"],
    *,
    order_id: int,
    request: Request,
    response: Response,
    actor: User,
    session: AsyncSession,
    service: PaymentOperationService,
    idempotency_key: str,
) -> PaymentOperationResponse:
    await _require_empty_body(request)
    try:
        handler = service.capture_order if operation == "capture" else service.cancel_order
        result = await handler(
            session,
            order_id=order_id,
            client_key=idempotency_key,
            actor_user_id=actor.id,
        )
    except InvalidPaymentAttemptKeyError as error:
        raise _error(400, "Invalid Idempotency-Key") from error
    except (PaymentOperationConflictError, PaymentStateError) as error:
        raise _error(409, "Payment operation state conflict") from error
    except PaymentOperationInProgressError as error:
        raise _error(409, "Payment operation is already in progress", retry_after=2) from error
    except PaymentOperationDisabledError as error:
        raise _error(503, "Payment management is unavailable") from error
    except PaymentOperationFailedError as error:
        if error.outcome_unknown:
            raise _error(503, "Payment operation outcome is unknown", retry_after=2) from error
        raise _error(502, "Payment provider rejected the operation") from error
    except SQLAlchemyError as error:
        raise _error(503, "Payment storage is unavailable", retry_after=2) from error
    response.headers["Cache-Control"] = "no-store"
    return PaymentOperationResponse.model_validate(result)


async def _require_empty_body(request: Request) -> None:
    async for chunk in request.stream():
        if chunk:
            raise _error(400, "Payment operation body must be empty")


def _error(status_code: int, detail: str, *, retry_after: int | None = None) -> HTTPException:
    headers = {"Cache-Control": "no-store"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return HTTPException(status_code=status_code, detail=detail, headers=headers)
