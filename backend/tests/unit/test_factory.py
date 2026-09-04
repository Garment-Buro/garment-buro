from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import AppEnvironment, Settings
from app.db.session import DatabaseManager
from app.factory import create_app
from app.integrations.minio import MinioStorage


def test_factory_mounts_legacy_api_and_owns_lifespan() -> None:
    lifecycle = {"started": 0, "stopped": 0}

    @asynccontextmanager
    async def legacy_lifespan(_: FastAPI) -> AsyncIterator[None]:
        lifecycle["started"] += 1
        yield
        lifecycle["stopped"] += 1

    legacy = FastAPI(lifespan=legacy_lifespan)

    @legacy.get("/api/legacy-probe")
    async def legacy_probe() -> dict[str, str]:
        return {"source": "legacy"}

    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=False,
        database_url=None,
    )
    application = create_app(settings=settings, legacy_app=legacy)

    with TestClient(application) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {
            "status": "ready",
            "database": "legacy",
            "storage": "legacy",
        }
        assert client.get("/api/legacy-probe").json() == {"source": "legacy"}
        assert lifecycle == {"started": 1, "stopped": 0}

    assert lifecycle == {"started": 1, "stopped": 1}


def test_factory_leaves_persistent_cart_routes_disabled_by_default() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=False,
        database_url=None,
    )
    application = create_app(settings=settings)
    registered_paths = {route.path for route in application.routes}

    assert "/api/cart/{cart_id}" not in registered_paths
    assert "/api/crm/projects" not in registered_paths
    assert "/api/crm/files" not in registered_paths


def test_factory_keeps_crm_file_routes_off_when_other_crm_writes_are_enabled() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        identity_api_enabled=True,
        identity_migration_fingerprint="d" * 64,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key=base64.urlsafe_b64encode(b"n" * 32).decode(),
        crm_api_enabled=True,
        crm_writes_enabled=True,
    )
    application = create_app(settings=settings)
    registered_paths = {route.path for route in application.routes}

    assert "/api/crm/projects/{project_id}/status" in registered_paths
    assert "/api/crm/files" not in registered_paths
    assert "/api/crm/files/{attachment_id}/download" not in registered_paths


def test_factory_registers_guarded_payment_management_and_payout_routes() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        public_base_url="https://shop.example.test",
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        identity_api_enabled=True,
        identity_migration_fingerprint="a" * 64,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key="bm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm4=",
        yookassa_shop_id="shop-id",
        yookassa_api_key="payment-secret",
        payment_creation_enabled=True,
        payment_management_enabled=True,
        payment_webhook_v2_enabled=True,
        yookassa_receipt_tax_system_code=1,
        yookassa_receipt_product_vat_code=1,
        yookassa_receipt_delivery_vat_code=1,
        yookassa_receipt_product_payment_mode="full_payment",
        yookassa_receipt_delivery_payment_mode="full_payment",
        yookassa_receipt_product_subject="non_marked",
        yookassa_receipt_delivery_subject="service",
        yookassa_payout_agent_id="agent-id",
        yookassa_payout_api_key="payout-secret",
        yookassa_payouts_enabled=True,
    )
    application = create_app(settings=settings)
    registered = {
        (method, route.path)
        for route in application.routes
        for method in getattr(route, "methods", set())
    }

    assert {
        ("GET", "/api/payments/orders/{order_id}"),
        ("POST", "/api/payments/orders/{order_id}/capture"),
        ("POST", "/api/payments/orders/{order_id}/cancel"),
        ("POST", "/api/payouts"),
        ("GET", "/api/payouts/{payout_id}"),
        ("POST", "/api/payouts/{payout_id}/refresh"),
    } <= registered


def test_factory_registers_catalog_mutations_only_for_guarded_cutover() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        legacy_database_url="sqlite:///legacy.db",
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        catalog_reads_enabled=True,
        catalog_writes_enabled=True,
        catalog_migration_fingerprint="c" * 64,
        catalog_content_migration_fingerprint="e" * 64,
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="http://storage.test",
        identity_api_enabled=True,
        identity_migration_fingerprint="d" * 64,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key=base64.urlsafe_b64encode(b"n" * 32).decode(),
        carts_v2_enabled=True,
        carts_migration_fingerprint="f" * 64,
        crm_api_enabled=True,
        crm_writes_enabled=True,
        crm_files_enabled=True,
    )
    application = create_app(settings=settings)
    registered = {
        (method, route.path)
        for route in application.routes
        for method in getattr(route, "methods", set())
    }

    assert {
        ("POST", "/api/products"),
        ("PUT", "/api/products/{product_id}"),
        ("DELETE", "/api/products/{product_id}"),
        ("PUT", "/api/variants/{variant_id}"),
        ("POST", "/api/upload"),
        ("GET", "/api/settings"),
        ("PUT", "/api/settings"),
        ("GET", "/api/options"),
        ("PUT", "/api/options"),
        ("GET", "/admin"),
        ("GET", "/admin/{path:path}"),
        ("GET", "/api/cart/{cart_id}"),
        ("PUT", "/api/cart/{cart_id}"),
        ("DELETE", "/api/cart/{cart_id}"),
        ("GET", "/api/crm/projects"),
        ("GET", "/api/crm/projects/{project_id}"),
        ("GET", "/api/crm/reference/fabrics"),
        ("GET", "/api/crm/reference/garment-models"),
        ("PATCH", "/api/crm/projects/{project_id}/status"),
        ("PUT", "/api/crm/projects/{project_id}/assignment"),
        ("PATCH", "/api/crm/units/{unit_id}/status"),
        ("POST", "/api/crm/units/{unit_id}/plans"),
        ("PUT", "/api/crm/units/{unit_id}/assignment"),
        ("POST", "/api/crm/materials/fabrics/{fabric_id}/receipts"),
        ("POST", "/api/crm/materials/fabrics/{fabric_id}/adjustments"),
        ("POST", "/api/crm/materials/reservations"),
        ("POST", "/api/crm/materials/reservations/{reservation_id}/consume"),
        ("POST", "/api/crm/materials/reservations/{reservation_id}/release"),
        ("POST", "/api/crm/files"),
        ("GET", "/api/crm/files/{attachment_id}/download"),
    } <= registered


def test_readiness_checks_enabled_async_database() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
    )
    application = create_app(settings=settings)

    with TestClient(application) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "sqlite",
        "storage": "legacy",
    }


def test_readiness_returns_503_when_enabled_database_is_unavailable() -> None:
    class UnavailableDatabase(DatabaseManager):
        async def startup(self) -> None:
            return

        async def shutdown(self) -> None:
            return

        async def ping(self) -> bool:
            return False

    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url="postgresql+asyncpg://unavailable:unavailable@db/unavailable",
    )
    database = UnavailableDatabase(settings)
    application = create_app(settings=settings, database=database)

    with TestClient(application) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "postgresql",
        "storage": "legacy",
    }


def test_readiness_checks_enabled_minio_buckets() -> None:
    class AvailableClient:
        def bucket_exists(self, bucket_name: str) -> bool:
            return bucket_name in {
                "garment-buro-test-media",
                "garment-buro-test-crm-private",
            }

    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="http://storage.test",
    )
    storage = MinioStorage(settings, client=AvailableClient())
    application = create_app(settings=settings, storage=storage)

    with TestClient(application) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "legacy",
        "storage": "minio",
    }


def test_readiness_returns_503_when_minio_bucket_is_unavailable() -> None:
    class UnavailableClient:
        def bucket_exists(self, bucket_name: str) -> bool:
            return bucket_name == "garment-buro-test-media"

    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="http://storage.test",
    )
    storage = MinioStorage(settings, client=UnavailableClient())
    application = create_app(settings=settings, storage=storage)

    with TestClient(application) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "legacy",
        "storage": "minio",
    }
