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
from app.modules.catalog.dependencies import require_catalog_writer
from app.modules.catalog.editor_options import editor_options_router
from app.modules.catalog.migration.content import (
    CatalogContentMigrationService,
    LegacyCatalogContentPlanner,
)
from app.modules.catalog.models import CatalogAuditEvent, CatalogDocument, CatalogDocumentRevision
from app.modules.catalog.router import router as catalog_router
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
    application.include_router(media_write_router)
    application.include_router(editor_options_router("/api/catalog-editor", require_catalog_writer))

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
        assert client.get("/api/settings").status_code == 404
        assert client.put("/api/settings", json={}).status_code == 404
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
        assert client.get("/api/options").status_code == 404
        assert client.put("/api/options", headers=manager_headers, json={}).status_code == 404
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
            client.put(f"/api/variants/{variant_id}", headers=manager_headers, json={}).status_code
            == 404
        )
        payload["expected_version"] = created.json()["version"]
        assert payload["expected_version"] == 1
        for invalid in [None, True, 0, -1, "1", 1.5, 2_147_483_648]:
            invalid_body = {**payload, "expected_version": invalid}
            if invalid is None:
                invalid_body.pop("expected_version")
            assert (
                client.put(
                    f"/api/products/{product_id}", headers=manager_headers, json=invalid_body
                ).status_code
                == 422
            )
        payload["variants"][0].update({"id": variant_id, "size": "L", "stock_quantity": 1})
        changed = client.put(f"/api/products/{product_id}", headers=manager_headers, json=payload)
        assert changed.status_code == 200
        assert changed.json()["version"] == 2
        stale = client.put(f"/api/products/{product_id}", headers=manager_headers, json=payload)
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "catalog_product_version_conflict"
        assert (
            client.get(f"/api/products/{product_id}", headers=manager_headers).json()["version"]
            == 2
        )
        assert changed.json()["variants"][0]["id"] == variant_id
        assert (
            client.get(f"/api/products/{product_id}/variants", headers=manager_headers).status_code
            == 404
        )
        for path in [
            "/api/products",
            "/api/products/counts",
            f"/api/products/{product_id}",
            "/api/catalog-editor/models",
            "/api/catalog-editor/fabrics",
        ]:
            assert client.get(path).status_code == 401
            assert client.get(path, headers=customer_headers).status_code == 403
        for path in ["/api/catalog-editor/models", "/api/catalog-editor/fabrics"]:
            options = client.get(path, headers=manager_headers)
            assert options.status_code == 200 and options.headers["cache-control"] == "no-store"
            assert options.json() == {"items": [], "next_cursor": None}
            assert (
                client.get(path, headers=manager_headers, params={"limit": 101}).status_code == 422
            )
        assert (
            client.get("/api/catalog-editor/models/999", headers=manager_headers).status_code == 404
        )
        assert (
            client.get(
                "/api/catalog-editor/selected-fabrics?ids=0", headers=manager_headers
            ).status_code
            == 422
        )
        listed = client.get("/api/products", headers=manager_headers, params={"limit": 1})
        assert listed.status_code == 200
        assert listed.headers["cache-control"] == "no-store"
        assert [product["id"] for product in listed.json()["items"]] == [product_id]
        assert listed.json()["next_cursor"] is None
        assert listed.json()["items"][0]["variant_count"] == 1
        assert "variants" not in listed.json()["items"][0]
        assert listed.json()["items"][0]["community_count"] is None
        assert listed.json()["items"][0]["communities"] == []
        assert (
            client.get(f"/api/products/{product_id}", headers=manager_headers).json()["variants"][
                0
            ]["size"]
            == "L"
        )
        assert client.get("/api/products/counts", headers=manager_headers).json() == {
            "garment_buro": 1,
            "user": 0,
            "communities": None,
        }
        for params in [
            {"limit": 101},
            {"sort": "price"},
            {"cursor": "bad"},
            {"unknown": "ignored?"},
        ]:
            assert (
                client.get("/api/products", headers=manager_headers, params=params).status_code
                == 422
            )

        payload["expected_version"] = changed.json()["version"]
        payload["title"] = "Updated product"
        updated = client.put(
            f"/api/products/{product_id}",
            headers=manager_headers,
            json=payload,
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 3
        assert updated.json()["title"] == "Updated product"

        deleted = client.delete(
            f"/api/products/{product_id}",
            headers=manager_headers,
        )
        assert deleted.status_code == 200
        assert deleted.json() == {"status": "deleted"}
        assert client.get(f"/api/products/{product_id}", headers=manager_headers).status_code == 404

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
            settings_document = await session.get(CatalogDocument, "settings")
            options_document = await session.get(CatalogDocument, "options")
            assert settings_document is not None and settings_document.version == 1
            assert options_document is not None and options_document.version == 1
            revisions = list(
                await session.scalars(
                    select(CatalogDocumentRevision).where(CatalogDocumentRevision.version == 2)
                )
            )
            assert revisions == []
        await database.shutdown()

    asyncio.run(verify())
    assert len(minio_client.uploads) == 1
