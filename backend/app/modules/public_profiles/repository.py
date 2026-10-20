from sqlalchemy import func, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import UnicodeLower, unicode_contains
from app.modules.identity.models import User, UserStatus
from app.modules.media.models import MediaObject, MediaStatus
from app.modules.public_profiles.models import PublicUserProfile
from app.modules.public_profiles.schemas import PeopleQuery


def public_profiles():
    return (
        select(
            PublicUserProfile.id,
            PublicUserProfile.slug,
            PublicUserProfile.display_name,
            PublicUserProfile.bio,
            PublicUserProfile.avatar_media_id,
        )
        .join(User, User.id == PublicUserProfile.user_id)
        .where(
            PublicUserProfile.is_published.is_(True),
            User.status == UserStatus.ACTIVE.value,
        )
    )


class PublicProfileRepository:
    async def detach_avatar(self, session: AsyncSession, profile: PublicUserProfile) -> None:
        if profile.avatar_media_id is not None:
            await session.execute(
                update(MediaObject)
                .where(
                    MediaObject.id == profile.avatar_media_id,
                    MediaObject.uploaded_by_user_id == profile.user_id,
                    MediaObject.is_public.is_(False),
                    MediaObject.status == MediaStatus.READY.value,
                    MediaObject.object_key.startswith(f"profiles/{profile.user_id}/"),
                )
                .values(updated_at=func.now())
            )
        profile.avatar_media_id = None

    async def own(self, session: AsyncSession, user_id: int, *, lock: bool = False):
        statement = select(PublicUserProfile).where(PublicUserProfile.user_id == user_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return await session.scalar(statement)

    async def public(self, session: AsyncSession, slug: str):
        return (
            (await session.execute(public_profiles().where(PublicUserProfile.slug == slug)))
            .mappings()
            .one_or_none()
        )

    async def list_page(
        self,
        session: AsyncSession,
        query: PeopleQuery,
        *,
        after_id: int | None,
        after_name: str | None,
    ):
        statement = public_profiles()
        text = query.query.strip()
        if text:
            statement = statement.where(
                or_(
                    unicode_contains(PublicUserProfile.display_name, text),
                    unicode_contains(PublicUserProfile.bio, text),
                )
            )
        name = UnicodeLower(PublicUserProfile.display_name)
        if after_id is not None:
            statement = statement.where(
                tuple_(name, PublicUserProfile.id) > tuple_(UnicodeLower(after_name), after_id)
                if query.sort == "name"
                else PublicUserProfile.id < after_id
            )
        order = (
            (name.asc(), PublicUserProfile.id.asc())
            if query.sort == "name"
            else (PublicUserProfile.id.desc(),)
        )
        return (
            (await session.execute(statement.order_by(*order).limit(query.limit + 1)))
            .mappings()
            .all()
        )
