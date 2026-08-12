from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.catalog.content import (
    CatalogContentMigrationService,
    LegacyCatalogContentPlanner,
)
from app.modules.catalog.content_router import router as catalog_content_router
from app.modules.catalog.models import CatalogAuditEvent, CatalogDocument, CatalogDocumentRevision
from app.modules.catalog.router import router as catalog_router
from app.modules.catalog.router import variant_write_router
from app.modules.catalog.router import write_router as catalog_write_router
from app.modules.identity.factory import build_identity_service
from app.modules.identity.models import Role, RoleName, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.media.models import MediaObject
from app.modules.media.router import write_router as media_write_router
from tests.fakes.minio import FakeMinioClient

JWT_SECRET = "j" * 32


def _webp_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), (10, 20, 30)).save(buffer, format="WEBP")
    return buffer.getvalue()


def test_catalog_write_api_requires_rbac_and_links_uploaded_minio_media(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'catalog-api.db'}",
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.test",
        jwt_secret=JWT_SECRET,
        identity_otp_pepper="p" * 32,
        identity_legacy_token_grace_until=datetime.now(timezone.utc) + timedelta(days=1),
        media_max_upload_bytes=1024,
    )
    database = DatabaseManager(settings)
    minio_client = FakeMinioClient()
    storage = MinioStorage(settings, client=minio_client)
    identity = build_identity_service(settings)

    async def seed() -> None:
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            repository = IdentityRepository()
            await repository.ensure_system_authorization(session)
            customer = User(
                id=1,
                email="customer@example.test",
                email_normalized="customer@example.test",
            )
            manager = User(
                id=2,
                email="manager@example.test",
                email_normalized="manager@example.test",
            )
            session.add_all([customer, manager])
            await session.flush()
            customer_role = await session.scalar(
                select(Role).where(Role.name == RoleName.CUSTOMER.value)
            )
            manager_role = await session.scalar(
                select(Role).where(Role.name == RoleName.MANAGER.value)
            )
            assert customer_role is not None and manager_role is not None
            session.add_all(
                [
                    UserRole(user_id=customer.id, role_id=customer_role.id),
                    UserRole(user_id=manager.id, role_id=manager_role.id),
                ]
            )
            content_plan = LegacyCatalogContentPlanner().build(tmp_path / "uploads")
            await CatalogContentMigrationService().apply(session, content_plan)
            await session.commit()

    asyncio.run(seed())

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await storage.startup()
        try:
            yield
        finally:
            await storage.shutdown()
            await database.shutdown()

    application = FastAPI(lifespan=lifespan)
    application.state.settings = settings
    application.state.database = database
    application.state.storage = storage
    application.state.identity_service = identity
    application.include_router(catalog_router)
    application.include_router(catalog_write_router)
    application.include_router(variant_write_router)
    application.include_router(media_write_router)
    application.include_router(catalog_content_router)

    customer_token = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        JWT_SECRET,
        algorithm="HS256",
    )
    manager_token = jwt.encode(
        {"sub": "2", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        JWT_SECRET,
        algorithm="HS256",
    )
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    manager_headers = {"Authorization": f"Bearer {manager_token}"}

    with TestClient(application) as client:
        assert (
            client.post(
                "/api/products",
                json={"title": "Anonymous", "price": 1},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/products",
                headers=customer_headers,
                json={"title": "Denied", "price": 1},
            ).status_code
            == 403
        )
        assert (
            client.put(
                "/api/settings",
                headers=customer_headers,
                json={"logo_video_url": "/denied.mp4"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/upload",
                files={"file": ("anonymous.webp", _webp_bytes(), "image/webp")},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/upload",
                headers=customer_headers,
                files={"file": ("customer.webp", _webp_bytes(), "image/webp")},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/upload",
                headers=manager_headers,
                files={"file": ("oversized.bin", b"x" * 1025, "application/octet-stream")},
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/api/upload",
                headers=manager_headers,
                files={"file": ("vector.svg", b"<svg/>", "image/svg+xml")},
            ).status_code
            == 415
        )
        assert (
            client.put(
                "/api/settings",
                headers=manager_headers,
                json={"logo_video_url": "javascript:alert(1)"},
            ).status_code
            == 422
        )

        upload = client.post(
            "/api/upload",
            headers=manager_headers,
            files={"file": ("source.png", _webp_bytes(), "image/png")},
        )
        assert upload.status_code == 200
        media_url = upload.json()["url"]
        assert media_url.startswith("https://cdn.test/garment-buro-test-media/catalog/")

        payload = {
            "title": "Managed product",
            "price": 12000,
            "sizes": "S,M",
            "colors": "black",
            "stock_quantity": 3,
            "mobile_card_image": media_url,
            "variants": [
                {
                    "size": "M",
                    "color": "black",
                    "stock_quantity": 2,
                    "preview_image": media_url,
                }
            ],
        }
        created = client.post("/api/products", headers=manager_headers, json=payload)
        assert created.status_code == 200
        product_id = created.json()["id"]
        assert created.json()["mobile_card_image"] == media_url
        assert created.json()["variants"][0]["preview_image"] == media_url
        variant_id = created.json()["variants"][0]["id"]

        assert (
            client.put(
                f"/api/variants/{variant_id}",
                headers=customer_headers,
                json={"size": "L", "color": "black", "stock_quantity": 1},
            ).status_code
            == 403
        )
        updated_variant = client.put(
            f"/api/variants/{variant_id}",
            headers=manager_headers,
            json={
                "size": "L",
                "color": "black",
                "stock_quantity": 1,
                "preview_image": media_url,
            },
        )
        assert updated_variant.status_code == 200
        assert updated_variant.json()["id"] == variant_id
        assert updated_variant.json()["size"] == "L"
        listed_variants = client.get(f"/api/products/{product_id}/variants")
        assert listed_variants.status_code == 200
        assert [variant["id"] for variant in listed_variants.json()] == [variant_id]
        assert listed_variants.json()[0]["size"] == "L"

        listed = client.get("/api/products")
        assert listed.status_code == 200
        assert [product["id"] for product in listed.json()] == [product_id]

        payload["title"] = "Updated product"
        updated = client.put(
            f"/api/products/{product_id}",
            headers=manager_headers,
            json=payload,
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Updated product"

        deleted = client.delete(
            f"/api/products/{product_id}",
            headers=manager_headers,
        )
        assert deleted.status_code == 200
        assert deleted.json() == {"status": "deleted"}
        assert client.get(f"/api/products/{product_id}").status_code == 404

        current_settings = client.get("/api/settings")
        assert current_settings.status_code == 200
        settings_payload = current_settings.json()
        settings_payload["logo_video_url"] = media_url
        saved_settings = client.put(
            "/api/settings",
            headers=manager_headers,
            json=settings_payload,
        )
        assert saved_settings.status_code == 200
        assert saved_settings.json()["logo_video_url"] == media_url

        saved_options = client.put(
            "/api/options",
            headers=manager_headers,
            json={
                "colors": [{"label": "Серый", "hex": "#808080"}],
                "sizes": ["M", "L"],
            },
        )
        assert saved_options.status_code == 200
        assert saved_options.json()["sizes"] == ["M", "L"]

    async def verify() -> None:
        await database.startup()
        async with database.session() as session:
            uploaded = await session.scalar(select(MediaObject))
            assert uploaded is not None
            assert uploaded.uploaded_by_user_id == 2
            audits = list(
                await session.scalars(select(CatalogAuditEvent).order_by(CatalogAuditEvent.id))
            )
            assert [audit.action for audit in audits] == [
                "product.created",
                "product.updated",
                "product.updated",
                "product.deleted",
            ]
            assert audits[1].details["scope"] == "variant"
            settings_document = await session.get(CatalogDocument, "settings")
            options_document = await session.get(CatalogDocument, "options")
            assert settings_document is not None and settings_document.version == 2
            assert options_document is not None and options_document.version == 2
            revisions = list(
                await session.scalars(
                    select(CatalogDocumentRevision).where(CatalogDocumentRevision.version == 2)
                )
            )
            assert len(revisions) == 2
            assert all(revision.actor_user_id == 2 for revision in revisions)
        await database.shutdown()

    asyncio.run(verify())
    assert len(minio_client.uploads) == 1
