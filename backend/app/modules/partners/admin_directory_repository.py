from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import unicode_contains
from app.modules.partners.admin_directory_schemas import AdminLandingQuery
from app.modules.partners.models import PartnerLanding, PartnerLandingProduct, PartnerProfile


class AdminLandingRepository:
    @staticmethod
    async def list_page(session: AsyncSession, query: AdminLandingQuery, after_id: int | None):
        product_count = (
            select(func.count())
            .where(PartnerLandingProduct.landing_id == PartnerLanding.id)
            .correlate(PartnerLanding)
            .scalar_subquery()
        )
        statement = select(
            PartnerLanding.id,
            PartnerLanding.version,
            PartnerLanding.title,
            PartnerLanding.slug,
            PartnerLanding.image_url,
            PartnerLanding.status,
            PartnerLanding.partner_id,
            PartnerProfile.display_name.label("partner_name"),
            product_count.label("product_count"),
        ).join(PartnerProfile, PartnerProfile.id == PartnerLanding.partner_id)
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(PartnerLanding.title, query.query),
                    unicode_contains(PartnerLanding.slug, query.query),
                    unicode_contains(PartnerProfile.display_name, query.query),
                )
            )
        if query.status:
            statement = statement.where(PartnerLanding.status == query.status)
        if after_id is not None:
            statement = statement.where(PartnerLanding.id < after_id)
        return (
            (
                await session.execute(
                    statement.order_by(PartnerLanding.id.desc()).limit(query.limit + 1)
                )
            )
            .mappings()
            .all()
        )
