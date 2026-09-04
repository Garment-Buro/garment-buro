from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.identity.models import Role, RoleName, UserRole
from app.modules.orders.models import Order
from app.modules.partners.models import (
    PartnerCommission,
    PartnerCommissionStatus,
    PartnerLanding,
    PartnerLandingStatus,
    PartnerOrderAttribution,
    PartnerPayoutRequest,
    PartnerPayoutStatus,
    PartnerProfile,
    PartnerStatus,
    PartnerVisit,
)


class PartnerRepository:
    async def get_profile_by_user(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        for_update: bool = False,
    ) -> PartnerProfile | None:
        statement = select(PartnerProfile).where(PartnerProfile.user_id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def get_profile(
        self,
        session: AsyncSession,
        *,
        partner_id: int,
        for_update: bool = False,
    ) -> PartnerProfile | None:
        statement = select(PartnerProfile).where(PartnerProfile.id == partner_id)
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def get_profile_by_code(
        self,
        session: AsyncSession,
        *,
        code: str,
    ) -> PartnerProfile | None:
        return await session.scalar(select(PartnerProfile).where(PartnerProfile.code == code))

    async def list_profiles(self, session: AsyncSession) -> list[PartnerProfile]:
        return list(
            await session.scalars(select(PartnerProfile).order_by(PartnerProfile.created_at.desc()))
        )

    @staticmethod
    async def add_profile(session: AsyncSession, profile: PartnerProfile) -> None:
        session.add(profile)
        await session.flush()

    async def assign_partner_role(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        assigned_by_user_id: int,
    ) -> None:
        role_id = await session.scalar(select(Role.id).where(Role.name == RoleName.PARTNER.value))
        if role_id is None:
            raise RuntimeError("Partner system role is not initialized")
        values = {
            "user_id": user_id,
            "role_id": role_id,
            "assigned_by_user_id": assigned_by_user_id,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(UserRole).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(UserRole).values(**values)
        else:
            raise RuntimeError("Partner role assignment requires PostgreSQL or SQLite")
        await session.execute(
            statement.on_conflict_do_nothing(index_elements=[UserRole.user_id, UserRole.role_id])
        )

    async def get_published_landing_by_slug(
        self,
        session: AsyncSession,
        *,
        slug: str,
    ) -> PartnerLanding | None:
        return await session.scalar(
            select(PartnerLanding)
            .join(PartnerProfile, PartnerProfile.id == PartnerLanding.partner_id)
            .where(
                PartnerLanding.slug == slug,
                PartnerLanding.status == PartnerLandingStatus.PUBLISHED.value,
                PartnerProfile.status == PartnerStatus.ACTIVE.value,
            )
            .options(selectinload(PartnerLanding.partner))
        )

    async def get_landing(
        self,
        session: AsyncSession,
        *,
        landing_id: int,
    ) -> PartnerLanding | None:
        return await session.scalar(
            select(PartnerLanding)
            .where(PartnerLanding.id == landing_id)
            .options(selectinload(PartnerLanding.partner))
        )

    async def get_landing_by_slug(
        self,
        session: AsyncSession,
        *,
        slug: str,
    ) -> PartnerLanding | None:
        return await session.scalar(select(PartnerLanding).where(PartnerLanding.slug == slug))

    @staticmethod
    async def add_landing(session: AsyncSession, landing: PartnerLanding) -> None:
        session.add(landing)
        await session.flush()

    async def list_landings(
        self,
        session: AsyncSession,
        *,
        partner_id: int,
    ) -> list[PartnerLanding]:
        return list(
            await session.scalars(
                select(PartnerLanding)
                .where(PartnerLanding.partner_id == partner_id)
                .order_by(PartnerLanding.created_at.desc())
            )
        )

    async def add_visit_once_per_day(
        self,
        session: AsyncSession,
        visit: PartnerVisit,
    ) -> None:
        values = {
            "landing_id": visit.landing_id,
            "visitor_digest": visit.visitor_digest,
            "visited_on": visit.visited_on,
            "created_at": visit.created_at,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(PartnerVisit).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(PartnerVisit).values(**values)
        else:
            raise RuntimeError("Partner visit intake requires PostgreSQL or SQLite")
        await session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[
                    PartnerVisit.landing_id,
                    PartnerVisit.visitor_digest,
                    PartnerVisit.visited_on,
                ]
            )
        )

    async def get_order_for_update(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> Order | None:
        return await session.scalar(select(Order).where(Order.id == order_id).with_for_update())

    async def get_attribution_by_order(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> PartnerOrderAttribution | None:
        return await session.scalar(
            select(PartnerOrderAttribution).where(PartnerOrderAttribution.order_id == order_id)
        )

    @staticmethod
    async def add_attribution(
        session: AsyncSession,
        attribution: PartnerOrderAttribution,
    ) -> None:
        session.add(attribution)
        await session.flush()

    async def get_commission_by_order(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> PartnerCommission | None:
        return await session.scalar(
            select(PartnerCommission).where(PartnerCommission.order_id == order_id)
        )

    @staticmethod
    async def add_commission(
        session: AsyncSession,
        commission: PartnerCommission,
    ) -> None:
        session.add(commission)
        await session.flush()

    async def list_partner_commissions(
        self,
        session: AsyncSession,
        *,
        partner_id: int,
        limit: int = 100,
    ) -> list[PartnerCommission]:
        return list(
            await session.scalars(
                select(PartnerCommission)
                .where(PartnerCommission.partner_id == partner_id)
                .order_by(PartnerCommission.created_at.desc())
                .limit(limit)
            )
        )

    async def list_partner_payouts(
        self,
        session: AsyncSession,
        *,
        partner_id: int,
        limit: int = 100,
    ) -> list[PartnerPayoutRequest]:
        return list(
            await session.scalars(
                select(PartnerPayoutRequest)
                .where(PartnerPayoutRequest.partner_id == partner_id)
                .order_by(PartnerPayoutRequest.created_at.desc())
                .limit(limit)
            )
        )

    async def get_payout_for_update(
        self,
        session: AsyncSession,
        *,
        payout_id: int,
    ) -> PartnerPayoutRequest | None:
        return await session.scalar(
            select(PartnerPayoutRequest)
            .where(PartnerPayoutRequest.id == payout_id)
            .with_for_update()
        )

    @staticmethod
    async def add_payout(
        session: AsyncSession,
        payout: PartnerPayoutRequest,
    ) -> None:
        session.add(payout)
        await session.flush()

    async def dashboard_totals(
        self,
        session: AsyncSession,
        *,
        partner_id: int,
        now: datetime,
    ) -> dict[str, Decimal | int]:
        visits = int(
            await session.scalar(
                select(func.count())
                .select_from(PartnerVisit)
                .join(PartnerLanding, PartnerLanding.id == PartnerVisit.landing_id)
                .where(PartnerLanding.partner_id == partner_id)
            )
            or 0
        )
        orders = int(
            await session.scalar(
                select(func.count())
                .select_from(PartnerOrderAttribution)
                .where(PartnerOrderAttribution.partner_id == partner_id)
            )
            or 0
        )
        earned = await self._sum_commissions(session, partner_id=partner_id)
        matured = await self._sum_commissions(
            session,
            partner_id=partner_id,
            available_before=now,
        )
        reserved = Decimal(
            await session.scalar(
                select(func.coalesce(func.sum(PartnerPayoutRequest.amount), 0)).where(
                    PartnerPayoutRequest.partner_id == partner_id,
                    PartnerPayoutRequest.status.in_(
                        (
                            PartnerPayoutStatus.REQUESTED.value,
                            PartnerPayoutStatus.APPROVED.value,
                            PartnerPayoutStatus.PAID.value,
                        )
                    ),
                )
            )
            or 0
        )
        paid = Decimal(
            await session.scalar(
                select(func.coalesce(func.sum(PartnerPayoutRequest.amount), 0)).where(
                    PartnerPayoutRequest.partner_id == partner_id,
                    PartnerPayoutRequest.status == PartnerPayoutStatus.PAID.value,
                )
            )
            or 0
        )
        return {
            "visits": visits,
            "orders": orders,
            "earned": earned,
            "available": max(Decimal("0.00"), matured - reserved),
            "paid": paid,
        }

    async def _sum_commissions(
        self,
        session: AsyncSession,
        *,
        partner_id: int,
        available_before: datetime | None = None,
    ) -> Decimal:
        statement = select(func.coalesce(func.sum(PartnerCommission.amount), 0)).where(
            PartnerCommission.partner_id == partner_id,
            PartnerCommission.status == PartnerCommissionStatus.PENDING.value,
        )
        if available_before is not None:
            statement = statement.where(PartnerCommission.available_at <= available_before)
        return Decimal(await session.scalar(statement) or 0)
