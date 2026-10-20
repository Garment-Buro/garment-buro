from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.public_policy import public_product_ids
from app.modules.customer_projects.models import CustomerProject, CustomerProjectMedia
from app.modules.media.models import MediaObject, MediaStatus, ProductMedia, ProductVariantMedia

SUMMARY_COLUMNS = (
    CustomerProject.id,
    CustomerProject.product_id,
    CustomerProject.kind,
    CustomerProject.title,
    CustomerProject.version,
    CustomerProject.created_at,
    CustomerProject.updated_at,
)


class ProjectRepository:
    async def creation_receipt(
        self, session: AsyncSession, *, user_id: int, client_key: str
    ) -> Mapping[str, Any] | None:
        result = await session.execute(
            select(*SUMMARY_COLUMNS, CustomerProject.deleted_at).where(
                CustomerProject.user_id == user_id, CustomerProject.client_key == client_key
            )
        )
        return result.mappings().one_or_none()

    async def get_by_key(
        self, session: AsyncSession, *, user_id: int, client_key: str
    ) -> CustomerProject | None:
        return await session.scalar(
            select(CustomerProject)
            .where(CustomerProject.user_id == user_id, CustomerProject.client_key == client_key)
            .execution_options(populate_existing=True)
        )

    async def get_owned(
        self, session: AsyncSession, *, user_id: int, project_id: int
    ) -> CustomerProject | None:
        return await session.scalar(
            select(CustomerProject)
            .where(CustomerProject.id == project_id, CustomerProject.user_id == user_id)
            .execution_options(populate_existing=True)
        )

    async def product_is_available(self, session: AsyncSession, *, product_id: int) -> bool:
        return (
            await session.scalar(public_product_ids().where(Product.id == product_id)) is not None
        )

    async def allowed_media_ids(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        product_id: int | None,
        media_ids: set[int],
        private_bucket: str,
        project_id: int | None = None,
    ) -> set[int]:
        own_upload = and_(
            MediaObject.uploaded_by_user_id == user_id,
            MediaObject.is_public.is_(False),
            MediaObject.bucket_name == private_bucket,
            MediaObject.object_key.startswith(f"projects/{user_id}/"),
        )
        product_image = (
            and_(
                MediaObject.is_public.is_(True),
                or_(
                    MediaObject.id.in_(
                        select(ProductMedia.media_object_id).where(
                            ProductMedia.product_id == product_id
                        )
                    ),
                    MediaObject.id.in_(
                        select(ProductVariantMedia.media_object_id)
                        .join(ProductVariant)
                        .where(ProductVariant.product_id == product_id)
                    ),
                ),
            )
            if product_id is not None
            else False
        )
        retained = (
            MediaObject.id.in_(
                select(CustomerProjectMedia.media_object_id).where(
                    CustomerProjectMedia.project_id == project_id
                )
            )
            if project_id is not None
            else False
        )
        previous_ids = (
            select(CustomerProjectMedia.media_object_id).where(
                CustomerProjectMedia.project_id == project_id
            )
            if project_id is not None
            else select(CustomerProjectMedia.media_object_id).where(False)
        )
        allowed = and_(
            MediaObject.id.in_(media_ids),
            MediaObject.status == MediaStatus.READY.value,
            MediaObject.content_type.in_(("image/jpeg", "image/png", "image/webp")),
            or_(own_upload, product_image, retained),
        )
        # Lock the union in stable order, including media detached by this edit.
        rows = await session.execute(
            select(MediaObject.id, allowed.label("allowed"))
            .where(
                or_(MediaObject.id.in_(media_ids), MediaObject.id.in_(previous_ids)),
            )
            .order_by(MediaObject.id)
            .with_for_update()
        )
        return {row.id for row in rows if row.allowed}

    async def create_once(
        self, session: AsyncSession, *, user_id: int, values: dict[str, Any]
    ) -> tuple[CustomerProject, bool]:
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            insert = postgresql_insert
        elif dialect == "sqlite":
            insert = sqlite_insert
        else:
            raise RuntimeError("Customer projects require PostgreSQL or SQLite")
        inserted = await session.scalar(
            insert(CustomerProject)
            .values(user_id=user_id, **values)
            .on_conflict_do_nothing(index_elements=["user_id", "client_key"])
            .returning(CustomerProject.id)
        )
        record = await self.get_by_key(session, user_id=user_id, client_key=values["client_key"])
        if record is None:
            raise RuntimeError("Inserted customer project is unavailable")
        return record, inserted is not None

    async def replace_media(
        self, session: AsyncSession, *, project_id: int, media_ids: set[int]
    ) -> None:
        previous_ids = set(
            await session.scalars(
                select(MediaObject.id)
                .where(
                    MediaObject.id.in_(
                        select(CustomerProjectMedia.media_object_id).where(
                            CustomerProjectMedia.project_id == project_id,
                        )
                    ),
                )
                .order_by(MediaObject.id)
                .with_for_update()
            )
        )
        await session.execute(
            delete(CustomerProjectMedia).where(CustomerProjectMedia.project_id == project_id)
        )
        detached = previous_ids - media_ids
        if detached:
            await session.execute(
                update(MediaObject)
                .where(MediaObject.id.in_(detached))
                .values(
                    updated_at=func.now(),
                )
            )
        session.add_all(
            CustomerProjectMedia(project_id=project_id, media_object_id=media_id)
            for media_id in sorted(media_ids)
        )
        await session.flush()

    async def update_version(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        project_id: int,
        expected_version: int,
        values: dict[str, Any],
    ) -> CustomerProject | None:
        return await session.scalar(
            update(CustomerProject)
            .where(
                CustomerProject.id == project_id,
                CustomerProject.user_id == user_id,
                CustomerProject.deleted_at.is_(None),
                CustomerProject.version == expected_version,
            )
            .values(version=CustomerProject.version + 1, updated_at=func.now(), **values)
            .returning(CustomerProject)
            .execution_options(populate_existing=True)
        )

    async def list_page(
        self, session: AsyncSession, *, user_id: int, kind: str, cursor: int | None, limit: int
    ) -> list[Mapping[str, Any]]:
        query = select(*SUMMARY_COLUMNS).where(
            CustomerProject.user_id == user_id,
            CustomerProject.kind == kind,
            CustomerProject.deleted_at.is_(None),
        )
        if cursor is not None:
            query = query.where(CustomerProject.id < cursor)
        return list(
            (
                await session.execute(query.order_by(CustomerProject.id.desc()).limit(limit))
            ).mappings()
        )
