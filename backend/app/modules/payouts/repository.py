from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payouts.models import Payout


class PayoutRepository:
    async def get(self, session: AsyncSession, *, payout_id: int) -> Payout | None:
        return await session.get(Payout, payout_id)

    async def get_for_update(self, session: AsyncSession, *, payout_id: int) -> Payout | None:
        return await session.scalar(select(Payout).where(Payout.id == payout_id).with_for_update())

    async def get_by_client_digest(
        self,
        session: AsyncSession,
        *,
        client_key_digest_sha256: str,
        for_update: bool = False,
    ) -> Payout | None:
        statement = select(Payout).where(
            Payout.client_key_digest_sha256 == client_key_digest_sha256
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def add(self, session: AsyncSession, payout: Payout) -> tuple[Payout, bool]:
        try:
            async with session.begin_nested():
                session.add(payout)
                await session.flush()
            return payout, True
        except IntegrityError:
            existing = await self.get_by_client_digest(
                session,
                client_key_digest_sha256=payout.client_key_digest_sha256,
                for_update=True,
            )
            if existing is None:
                raise
            return existing, False
