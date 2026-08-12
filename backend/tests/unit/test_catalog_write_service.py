from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import CatalogAuditEvent, Product
from app.modules.catalog.schemas import ProductWriteRequest
from app.modules.catalog.service import CatalogWriteService, UnknownCatalogMediaError
from app.modules.identity.models import User
from app.modules.media.models import MediaObject, MediaStatus


def _settings(database_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.test",
    )


def _payload(*, title: str, media_url: str) -> ProductWriteRequest:
    return ProductWriteRequest.model_validate(
        {
            "title": title,
            "price": 12000,
            "old_price": 15000,
            "description": "Description",
            "sizes": "S,M",
            "colors": "black,white",
            "stock_quantity": 4,
            "desktop_slider_images": media_url,
            "mobile_card_image": media_url,
            "variants": [
                {
                    "id": 999,
                    "size": "M",
                    "color": "black",
                    "color_hex": "#1A1A1A",
                    "stock_quantity": 2,
                    "width_cm": 60,
                    "height_cm": 72,
                    "preview_image": media_url,
                    "images": media_url,
                }
            ],
        }
    )


def test_catalog_write_service_replaces_normalized_children_and_keeps_audit(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "catalog-write.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                actor = User(
                    id=10,
                    email="manager@example.test",
                    email_normalized="manager@example.test",
                )
                first = MediaObject(
                    bucket_name=settings.minio_media_bucket,
                    object_key="uploads/first.webp",
                    original_filename="first.webp",
                    content_type="image/webp",
                    size_bytes=10,
                    checksum_sha256="a" * 64,
                    status=MediaStatus.READY.value,
                )
                second = MediaObject(
                    bucket_name=settings.minio_media_bucket,
                    object_key="uploads/second.webp",
                    original_filename="second.webp",
                    content_type="image/webp",
                    size_bytes=11,
                    checksum_sha256="b" * 64,
                    status=MediaStatus.READY.value,
                )
                session.add_all([actor, first, second])
                await session.commit()

            service = CatalogWriteService(settings)
            async with database.session() as session:
                created = await service.create_product(
                    session,
                    payload=_payload(title="Created", media_url="/uploads/first.webp"),
                    actor_user_id=10,
                )
                await session.commit()
                product_id = created.id
                assert created.desktop_slider_images == "/uploads/first.webp"
                assert created.variants[0].id != 999

            second_url = (
                f"{settings.minio_public_base_url}/{settings.minio_media_bucket}/"
                "uploads/second.webp"
            )
            async with database.session() as session:
                updated = await service.update_product(
                    session,
                    product_id=product_id,
                    payload=_payload(title="Updated", media_url=second_url),
                    actor_user_id=10,
                )
                await session.commit()
                assert updated.title == "Updated"
                assert updated.mobile_card_image == "/uploads/second.webp"
                assert len(updated.variants) == 1

            async with database.session() as session:
                await service.delete_product(
                    session,
                    product_id=product_id,
                    actor_user_id=10,
                )
                await session.commit()

            async with database.session() as session:
                assert await session.scalar(select(func.count(Product.id))) == 0
                audits = list(
                    await session.scalars(select(CatalogAuditEvent).order_by(CatalogAuditEvent.id))
                )
                assert [audit.action for audit in audits] == [
                    "product.created",
                    "product.updated",
                    "product.deleted",
                ]
                assert all(audit.actor_user_id == 10 for audit in audits)
                assert all(len(audit.snapshot_checksum_sha256) == 64 for audit in audits)
                assert await session.scalar(select(func.count(MediaObject.id))) == 2
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_catalog_write_service_rejects_unknown_media_atomically(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "unknown-media.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                session.add(
                    User(
                        id=10,
                        email="manager@example.test",
                        email_normalized="manager@example.test",
                    )
                )
                await session.commit()

            service = CatalogWriteService(settings)
            async with database.session() as session:
                try:
                    await service.create_product(
                        session,
                        payload=_payload(
                            title="Unknown",
                            media_url="/uploads/missing.webp",
                        ),
                        actor_user_id=10,
                    )
                except UnknownCatalogMediaError:
                    await session.rollback()
                else:
                    raise AssertionError("Unknown media must reject the catalog write")

            async with database.session() as session:
                assert await session.scalar(select(func.count(Product.id))) == 0
                assert await session.scalar(select(func.count(CatalogAuditEvent.id))) == 0
        finally:
            await database.shutdown()

    asyncio.run(scenario())
