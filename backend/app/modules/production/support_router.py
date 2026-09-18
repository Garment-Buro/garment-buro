from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.identity.models import User
from app.modules.identity.router import get_current_identity_user
from app.modules.production.inbox_schemas import SupportRequestCreate, SupportRequestCreated
from app.modules.production.inbox_service import (
    AdminInboxService,
    SupportOrderNotFoundError,
    SupportRateLimitError,
)

router = APIRouter(prefix="/api/support", tags=["support"])


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
