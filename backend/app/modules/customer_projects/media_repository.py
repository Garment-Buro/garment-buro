from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customer_projects.models import CustomerProject, CustomerProjectMedia
from app.modules.media.models import MediaObject, MediaStatus
from app.modules.media.repository import MediaRepository


class ProjectMediaRepository(MediaRepository):
    async def get_project_images(
        self, session: AsyncSession, *, user_id: int, project_id: int, version: int
    ) -> list[MediaObject]:
        return list(
            await session.scalars(
                select(MediaObject)
                .join(CustomerProjectMedia, CustomerProjectMedia.media_object_id == MediaObject.id)
                .join(CustomerProject, CustomerProject.id == CustomerProjectMedia.project_id)
                .where(
                    CustomerProject.id == project_id,
                    CustomerProject.user_id == user_id,
                    CustomerProject.deleted_at.is_(None),
                    CustomerProject.version == version,
                )
                .order_by(MediaObject.id)
            )
        )

    async def get_project_version(
        self, session: AsyncSession, *, user_id: int, project_id: int
    ) -> int | None:
        return await session.scalar(
            select(CustomerProject.version).where(
                CustomerProject.id == project_id,
                CustomerProject.user_id == user_id,
                CustomerProject.deleted_at.is_(None),
            )
        )

    async def get_owned_ready(
        self, session: AsyncSession, *, user_id: int, media_id: int, bucket_name: str
    ) -> MediaObject | None:
        return await session.scalar(
            select(MediaObject).where(
                MediaObject.id == media_id,
                MediaObject.uploaded_by_user_id == user_id,
                MediaObject.bucket_name == bucket_name,
                MediaObject.object_key.startswith(f"projects/{user_id}/"),
                MediaObject.is_public.is_(False),
                MediaObject.status == MediaStatus.READY.value,
                MediaObject.content_type.in_(("image/jpeg", "image/png", "image/webp")),
            )
        )
