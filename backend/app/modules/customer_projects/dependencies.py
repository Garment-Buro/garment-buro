from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.identity.models import User
from app.modules.identity.router import get_current_identity_user

Session = Annotated[AsyncSession, Depends(get_database_session)]
CurrentUser = Annotated[User, Depends(get_current_identity_user)]
ResourceId = Annotated[int, Path(gt=0, le=2_147_483_647)]
