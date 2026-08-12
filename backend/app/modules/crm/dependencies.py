from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.identity.exceptions import PermissionDeniedError
from app.modules.identity.models import PermissionCode, User
from app.modules.identity.router import get_current_identity_user, get_identity_service
from app.modules.identity.service import IdentityService


async def require_crm_reader(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> User:
    try:
        await identity.require_permission(
            session,
            user_id=user.id,
            permission=PermissionCode.CRM_ACCESS,
        )
    except PermissionDeniedError as error:
        raise HTTPException(status_code=403, detail="Forbidden") from error
    return user
