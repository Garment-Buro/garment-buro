from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, true, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import Product
from app.modules.catalog.public_policy import public_product_ids
from app.modules.identity.models import Role, RoleName, User, UserRole, UserStatus
from app.modules.orders.models import Order
from app.modules.partners.models import (
    PartnerCommission,
    PartnerCommissionStatus,
    PartnerLanding,
    PartnerLandingProduct,
    PartnerOrderAttribution,
    PartnerPayoutRequest,
    PartnerProfile,
    PartnerRequisites,
    PartnerStatus,
    PartnerVisit,
)
from app.modules.partners.public_policy import public_landing_conditions


class PartnerRepository:
    @staticmethod
    async def get_active_profile_by_user(
        session: AsyncSession, *, user_id: int
    ) -> PartnerProfile | None:
        return await session.scalar(
            select(PartnerProfile)
            .join(User, User.id == PartnerProfile.user_id)
            .where(
                PartnerProfile.user_id == user_id,
                PartnerProfile.status == PartnerStatus.ACTIVE.value,
                User.status == UserStatus.ACTIVE.value,
            )
            .execution_options(populate_existing=True)
        )

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
        return await session.scalar(statement.execution_options(populate_existing=True))

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
        return await session.scalar(statement.execution_options(populate_existing=True))

    @staticmethod
    async def profile_user_id(session: AsyncSession, *, partner_id: int) -> int | None:
        return await session.scalar(
            select(PartnerProfile.user_id).where(PartnerProfile.id == partner_id)
        )

    @staticmethod
    async def lock_landing_user(session: AsyncSession, *, user_id: int) -> str | None:
        return await session.scalar(select(User.status).where(User.id == user_id).with_for_update())

    @staticmethod
    async def landing_partner_id(session: AsyncSession, *, landing_id: int) -> int | None:
        return await session.scalar(
            select(PartnerLanding.partner_id).where(PartnerLanding.id == landing_id)
        )

    async def get_profile_by_code(
        self,
        session: AsyncSession,
        *,
        code: str,
    ) -> PartnerProfile | None:
        return await session.scalar(select(PartnerProfile).where(PartnerProfile.code == code))

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
            .join(User, User.id == PartnerProfile.user_id)
            .where(
                PartnerLanding.slug == slug,
                *public_landing_conditions(),
            )
            .options(
                selectinload(PartnerLanding.partner),
                selectinload(PartnerLanding.product_links),
            )
        )

    async def get_landing(
        self,
        session: AsyncSession,
        *,
        landing_id: int,
        partner_id: int | None = None,
    ) -> PartnerLanding | None:
        return await session.scalar(
            select(PartnerLanding)
            .where(
                PartnerLanding.id == landing_id,
                *([PartnerLanding.partner_id == partner_id] if partner_id is not None else []),
            )
            .execution_options(populate_existing=True)
            .options(
                selectinload(PartnerLanding.partner),
                selectinload(PartnerLanding.product_links),
            )
        )

    @staticmethod
    async def claim_landing_version(
        session: AsyncSession, *, landing_id: int, expected_version: int
    ) -> int | None:
        return await session.scalar(
            update(PartnerLanding)
            .where(PartnerLanding.id == landing_id, PartnerLanding.version == expected_version)
            .values(version=PartnerLanding.version + 1)
            .returning(PartnerLanding.version)
            .execution_options(synchronize_session=False)
        )

    @staticmethod
    async def selectable_product_ids(session: AsyncSession, *, product_ids: list[int]) -> set[int]:
        if not product_ids:
            return set()
        return set(await session.scalars(public_product_ids().where(Product.id.in_(product_ids))))

    @staticmethod
    async def list_owned_landing_page(
        session: AsyncSession, *, partner_id: int, limit: int, after_id: int | None
    ):
        product_count = (
            select(func.count())
            .where(PartnerLandingProduct.landing_id == PartnerLanding.id)
            .correlate(PartnerLanding)
            .scalar_subquery()
        )
        statement = select(
            PartnerLanding.id,
            PartnerLanding.version,
            PartnerLanding.slug,
            PartnerLanding.title,
            PartnerLanding.image_url,
            PartnerLanding.status,
            product_count.label("product_count"),
        ).where(PartnerLanding.partner_id == partner_id)
        if after_id is not None:
            statement = statement.where(PartnerLanding.id < after_id)
        return (
            (await session.execute(statement.order_by(PartnerLanding.id.desc()).limit(limit + 1)))
            .mappings()
            .all()
        )

    async def get_landing_by_slug(
        self,
        session: AsyncSession,
        *,
        slug: str,
    ) -> PartnerLanding | None:
        return await session.scalar(
            select(PartnerLanding)
            .where(PartnerLanding.slug == slug)
            .options(selectinload(PartnerLanding.product_links))
        )

    @staticmethod
    async def add_landing(session: AsyncSession, landing: PartnerLanding) -> None:
        session.add(landing)
        await session.flush()

    @staticmethod
    async def existing_product_ids(
        session: AsyncSession,
        *,
        product_ids: list[int],
    ) -> set[int]:
        if not product_ids:
            return set()
        return set(await session.scalars(select(Product.id).where(Product.id.in_(product_ids))))

    @staticmethod
    async def replace_landing_products(
        session: AsyncSession,
        *,
        landing: PartnerLanding,
        product_ids: list[int],
    ) -> None:
        landing.product_links.clear()
        await session.flush()
        landing.product_links.extend(
            PartnerLandingProduct(product_id=product_id, position=position)
            for position, product_id in enumerate(product_ids)
        )
        await session.flush()

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

    async def get_partner_requisites(
        self,
        session: AsyncSession,
        *,
        partner_id: int,
        for_update: bool = False,
    ) -> PartnerRequisites | None:
        statement = select(PartnerRequisites).where(PartnerRequisites.partner_id == partner_id)
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement.execution_options(populate_existing=True))

    @staticmethod
    async def add_partner_requisites(
        session: AsyncSession,
        requisites: PartnerRequisites,
    ) -> None:
        session.add(requisites)
        await session.flush()

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
            .execution_options(populate_existing=True)
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
    ) -> dict[str, Decimal | int | bool]:
        # Independent aggregate subqueries avoid visit/order/commission fan-out.
        # One SQL statement supplies one database snapshot for the entire balance.
        visits = (
            select(func.count())
            .select_from(PartnerVisit)
            .join(PartnerLanding, PartnerLanding.id == PartnerVisit.landing_id)
            .where(PartnerLanding.partner_id == partner_id)
            .scalar_subquery()
        )
        orders = (
            select(func.count())
            .select_from(PartnerOrderAttribution)
            .where(PartnerOrderAttribution.partner_id == partner_id)
            .scalar_subquery()
        )
        commissions = (
            select(
                func.coalesce(func.sum(PartnerCommission.amount), 0).label("earned"),
                func.coalesce(
                    func.sum(PartnerCommission.amount).filter(
                        PartnerCommission.available_at <= now
                    ),
                    0,
                ).label("matured"),
            )
            .where(
                PartnerCommission.partner_id == partner_id,
                PartnerCommission.status == PartnerCommissionStatus.PENDING.value,
            )
            .subquery()
        )
        payouts = (
            select(
                func.coalesce(
                    func.sum(PartnerPayoutRequest.amount).filter(
                        PartnerPayoutRequest.status.in_(("requested", "approved", "paid"))
                    ),
                    0,
                ).label("reserved"),
                func.coalesce(
                    func.sum(PartnerPayoutRequest.amount).filter(
                        PartnerPayoutRequest.status == "paid"
                    ),
                    0,
                ).label("paid"),
            )
            .where(PartnerPayoutRequest.partner_id == partner_id)
            .subquery()
        )
        has_requisites = (
            select(PartnerRequisites.id).where(PartnerRequisites.partner_id == partner_id).exists()
        )
        row = (
            await session.execute(
                select(
                    has_requisites.label("has_requisites"),
                    visits.label("visits"),
                    orders.label("orders"),
                    commissions.c.earned,
                    commissions.c.matured,
                    payouts.c.reserved,
                    payouts.c.paid,
                ).select_from(commissions.join(payouts, true()))
            )
        ).one()
        return {
            "has_requisites": bool(row.has_requisites),
            "visits": int(row.visits),
            "orders": int(row.orders),
            "earned": Decimal(row.earned),
            "available": max(Decimal("0.00"), Decimal(row.matured) - Decimal(row.reserved)),
            "paid": Decimal(row.paid),
        }
