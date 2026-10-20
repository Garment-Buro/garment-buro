from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import User, UserStatus
from app.modules.media.models import MediaObject, MediaStatus
from app.modules.media.repository import MediaRepository
from app.modules.public_profiles.models import PublicUserProfile


class AvatarRepository(MediaRepository):
    async def current_object(
        self,
        session: AsyncSession,
        *,
        media_id: int,
        bucket_name: str,
        user_id: int | None = None,
        slug: str | None = None,
    ):
        statement = (
            select(
                MediaObject.object_key,
                MediaObject.size_bytes,
                MediaObject.checksum_sha256,
                MediaObject.version_id,
                PublicUserProfile.user_id,
            )
            .select_from(PublicUserProfile)
            .join(User, User.id == PublicUserProfile.user_id)
            .join(MediaObject, MediaObject.id == PublicUserProfile.avatar_media_id)
            .where(
                MediaObject.id == media_id,
                MediaObject.provider == "minio",
                MediaObject.uploaded_by_user_id == PublicUserProfile.user_id,
                MediaObject.status == MediaStatus.READY.value,
                MediaObject.bucket_name == bucket_name,
                MediaObject.is_public.is_(False),
                MediaObject.content_type == "image/webp",
                User.status == UserStatus.ACTIVE.value,
            )
        )
        if user_id is not None:
            statement = statement.where(PublicUserProfile.user_id == user_id)
        else:
            statement = statement.where(
                PublicUserProfile.slug == slug, PublicUserProfile.is_published.is_(True)
            )
        return (await session.execute(statement)).mappings().one_or_none()
