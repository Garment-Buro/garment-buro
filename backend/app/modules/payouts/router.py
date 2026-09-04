from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.identity.models import User
from app.modules.payments.security import InvalidPaymentAttemptKeyError
from app.modules.payouts.dependencies import require_payout_manager
from app.modules.payouts.schemas import PayoutCreateCommand, PayoutResponse
from app.modules.payouts.service import (
    PayoutConflictError,
    PayoutDisabledError,
    PayoutInProgressError,
    PayoutNotFoundError,
    PayoutProviderFailedError,
    PayoutService,
)

router = APIRouter(prefix="/api/payouts", tags=["payouts"])


def get_payout_service(request: Request) -> PayoutService:
    service = request.app.state.payout_service
    if not isinstance(service, PayoutService):
        raise RuntimeError("Payout service is not initialized")
    return service


@router.post("", response_model=PayoutResponse, status_code=status.HTTP_201_CREATED)
async def create_payout(
    command: PayoutCreateCommand,
    response: Response,
    actor: Annotated[User, Depends(require_payout_manager)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PayoutService, Depends(get_payout_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> PayoutResponse:
    try:
        result = await service.create(
            session,
            command=command,
            client_key=idempotency_key,
            actor_user_id=actor.id,
        )
    except InvalidPaymentAttemptKeyError as error:
        raise _error(400, "Invalid Idempotency-Key") from error
    except PayoutConflictError as error:
        raise _error(409, "Payout state conflict") from error
    except PayoutInProgressError as error:
        raise _error(409, "Payout creation is already in progress", retry_after=2) from error
    except PayoutDisabledError as error:
        raise _error(503, "Payouts are unavailable") from error
    except PayoutProviderFailedError as error:
        if error.outcome_unknown:
            raise _error(503, "Payout outcome is unknown", retry_after=2) from error
        raise _error(502, "Payout provider rejected the request") from error
    except SQLAlchemyError as error:
        raise _error(503, "Payout storage is unavailable", retry_after=2) from error
    response.headers["Cache-Control"] = "no-store"
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/{payout_id}", response_model=PayoutResponse)
async def get_payout(
    payout_id: Annotated[int, Path(ge=1)],
    response: Response,
    _actor: Annotated[User, Depends(require_payout_manager)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PayoutService, Depends(get_payout_service)],
) -> PayoutResponse:
    try:
        result = await service.get(session, payout_id=payout_id)
    except PayoutNotFoundError as error:
        raise _error(404, "Payout not found") from error
    except PayoutDisabledError as error:
        raise _error(503, "Payouts are unavailable") from error
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/{payout_id}/refresh", response_model=PayoutResponse)
async def refresh_payout(
    payout_id: Annotated[int, Path(ge=1)],
    request: Request,
    response: Response,
    _actor: Annotated[User, Depends(require_payout_manager)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[PayoutService, Depends(get_payout_service)],
) -> PayoutResponse:
    await _require_empty_body(request)
    try:
        result = await service.refresh(session, payout_id=payout_id)
    except PayoutNotFoundError as error:
        raise _error(404, "Payout not found") from error
    except PayoutConflictError as error:
        raise _error(409, "Payout state conflict") from error
    except PayoutDisabledError as error:
        raise _error(503, "Payouts are unavailable") from error
    except PayoutProviderFailedError as error:
        raise _error(503 if error.outcome_unknown else 502, "Payout refresh failed") from error
    except SQLAlchemyError as error:
        raise _error(503, "Payout storage is unavailable", retry_after=2) from error
    response.headers["Cache-Control"] = "no-store"
    return result


async def _require_empty_body(request: Request) -> None:
    async for chunk in request.stream():
        if chunk:
            raise _error(400, "Payout refresh body must be empty")


def _error(status_code: int, detail: str, *, retry_after: int | None = None) -> HTTPException:
    headers = {"Cache-Control": "no-store"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return HTTPException(status_code=status_code, detail=detail, headers=headers)
