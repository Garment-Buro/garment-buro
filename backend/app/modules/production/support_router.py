from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.identity.models import User
from app.modules.identity.router import get_current_identity_user
from app.modules.production.inbox_schemas import SupportRequestCreate, SupportRequestCreated
from app.modules.production.inbox_service import (
    AdminInboxConflictError,
    AdminInboxNotFoundError,
    AdminInboxService,
    SupportOrderNotFoundError,
    SupportRateLimitError,
)
from app.modules.production.ticket_schemas import TicketReply
from app.modules.production.ticket_service import TicketService

router = APIRouter(prefix="/api/support", tags=["support"])
Customer = Annotated[User, Depends(get_current_identity_user)]
Session = Annotated[AsyncSession, Depends(get_database_session)]


@router.get("")
async def my_tickets(
    user: Customer, session: Session, response: Response, offset: int = Query(0, ge=0, le=1000000)
):
    response.headers["Cache-Control"] = "no-store"
    return await TicketService().customer_list(session, user.id, offset=offset)


@router.get("/{ticket_id}")
async def my_ticket(
    ticket_id: int,
    user: Customer,
    session: Session,
    response: Response,
    after: int = Query(0, ge=0),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        service = TicketService()
        item = await service.item(session, ticket_id, customer_id=user.id)
        return await service.detail(session, item, after=after)
    except AdminInboxNotFoundError as error:
        raise HTTPException(404, "Тикет не найден") from error


@router.post("/{ticket_id}/messages")
async def reply_to_ticket(ticket_id: int, payload: TicketReply, user: Customer, session: Session):
    try:
        result = await TicketService().reply(
            session, ticket_id=ticket_id, actor=user, payload=payload
        )
        await session.commit()
        return result
    except AdminInboxNotFoundError as error:
        await session.rollback()
        raise HTTPException(404, "Тикет не найден") from error
    except AdminInboxConflictError as error:
        await session.rollback()
        raise HTTPException(409, str(error)) from error


@router.post("", response_model=SupportRequestCreated, status_code=status.HTTP_201_CREATED)
async def create_support_request(
    payload: SupportRequestCreate,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
):
    try:
        item = await AdminInboxService().create_support_request(
            session,
            reporter=user,
            subject=payload.subject,
            message=payload.message,
            order_id=payload.order_id,
        )
        response = SupportRequestCreated(
            id=item.id,
            status=item.status,
            created_at=item.created_at,
        )
        await session.commit()
        return response
    except SupportOrderNotFoundError as error:
        await session.rollback()
        raise HTTPException(404, "Заказ не найден") from error
    except SupportRateLimitError as error:
        await session.rollback()
        raise HTTPException(429, str(error), headers={"Retry-After": "3600"}) from error
