from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import unicode_contains
from app.modules.partners.models import PartnerPayoutRequest, PartnerProfile
from app.modules.partners.read_schemas import AdminPartnerQuery, PartnerPayoutPosition


class PartnerReadRepository:
    @staticmethod
    async def profile_page(session: AsyncSession, query: AdminPartnerQuery, after_id: int | None):
        statement = select(
            PartnerProfile.id,
            PartnerProfile.user_id,
            PartnerProfile.code,
            PartnerProfile.display_name,
            PartnerProfile.status,
            PartnerProfile.commission_bps,
            PartnerProfile.created_at,
        )
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(PartnerProfile.display_name, query.query),
                    unicode_contains(PartnerProfile.code, query.query),
                )
            )
        if query.status:
            statement = statement.where(PartnerProfile.status == query.status)
        if query.selectable:
            statement = statement.where(PartnerProfile.status != "suspended")
        if after_id is not None:
            statement = statement.where(PartnerProfile.id < after_id)
        return (
            (
                await session.execute(
                    statement.order_by(PartnerProfile.id.desc()).limit(query.limit + 1)
                )
            )
            .mappings()
            .all()
        )

    @staticmethod
    async def payout_page(
        session: AsyncSession, partner_id: int, limit: int, position: PartnerPayoutPosition | None
    ):
        statement = select(
            PartnerPayoutRequest.id,
            PartnerPayoutRequest.amount,
            PartnerPayoutRequest.currency,
            PartnerPayoutRequest.status,
            PartnerPayoutRequest.reviewed_at,
            PartnerPayoutRequest.paid_at,
            PartnerPayoutRequest.note,
            PartnerPayoutRequest.created_at,
        ).where(PartnerPayoutRequest.partner_id == partner_id)
        if position is not None:
            statement = statement.where(
                or_(
                    PartnerPayoutRequest.created_at < position.created_at,
                    and_(
                        PartnerPayoutRequest.created_at == position.created_at,
                        PartnerPayoutRequest.id < position.id,
                    ),
                )
            )
        return (
            (
                await session.execute(
                    statement.order_by(
                        PartnerPayoutRequest.created_at.desc(), PartnerPayoutRequest.id.desc()
                    ).limit(limit + 1)
                )
            )
            .mappings()
            .all()
        )
