from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import User, UserStatus


async def lock_active_customer(session: AsyncSession, user_id: int) -> bool:
    """Serialize customer writes with account deletion, using fresh SQL status."""
    return (
        await session.scalar(
            select(User.id)
            .where(
                User.id == user_id,
                User.status == UserStatus.ACTIVE.value,
            )
            .with_for_update()
        )
        is not None
    )
