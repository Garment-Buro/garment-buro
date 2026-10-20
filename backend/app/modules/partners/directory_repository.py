from sqlalchemy import or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import UnicodeLower, unicode_contains
from app.modules.identity.models import User
from app.modules.partners.directory_schemas import CommunityQuery
from app.modules.partners.models import PartnerLanding, PartnerProfile
from app.modules.partners.public_policy import public_landing_conditions


def public_community_cards():
    return (
        select(
            PartnerLanding.id,
            PartnerLanding.slug,
            PartnerLanding.title,
            PartnerLanding.description,
            PartnerLanding.image_url,
            PartnerProfile.display_name.label("owner_name"),
        )
        .join(PartnerProfile, PartnerProfile.id == PartnerLanding.partner_id)
        .join(
            User,
            User.id == PartnerProfile.user_id,
        )
        .where(*public_landing_conditions())
    )


class CommunityDirectoryRepository:
    async def list_page(
        self,
        session: AsyncSession,
        *,
        query: CommunityQuery,
        after_id: int | None = None,
        after_title: str | None = None,
    ):
        # Scalar projection prevents loading landing content and collection relationships.
        statement = public_community_cards()
        text = query.query.strip()
        if text:
            statement = statement.where(
                or_(
                    unicode_contains(PartnerLanding.title, text),
                    unicode_contains(PartnerLanding.description, text),
                    unicode_contains(PartnerProfile.display_name, text),
                )
            )
        title = UnicodeLower(PartnerLanding.title)
        if after_id is not None:
            statement = statement.where(
                tuple_(title, PartnerLanding.id) > tuple_(UnicodeLower(after_title), after_id)
                if query.sort == "name"
                else PartnerLanding.id < after_id,
            )
        order = (
            (title.asc(), PartnerLanding.id.asc())
            if query.sort == "name"
            else (PartnerLanding.id.desc(),)
        )
        return (
            (await session.execute(statement.order_by(*order).limit(query.limit + 1)))
            .mappings()
            .all()
        )
