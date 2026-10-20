from __future__ import annotations

import asyncio
import base64

import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.session import DatabaseManager
from app.factory import create_app
from app.integrations.minio import MinioStorage


def test_factory_rejects_legacy_application() -> None:
    settings = Settings(_env_file=None, app_env="test")
    with pytest.raises(TypeError, match="legacy_app"):
        create_app(settings=settings, legacy_app=FastAPI())


def test_partial_database_startup_releases_engine() -> None:
    class FailingDatabase(DatabaseManager):
        async def startup(self) -> None:
            await super().startup()
            raise RuntimeError("database startup failed after allocation")

    settings = Settings(
        _env_file=None,
        app_env="test",
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
    )
    database = FailingDatabase(settings)
    application = create_app(settings=settings, database=database)
    with pytest.raises(RuntimeError, match="database startup failed"), TestClient(application):
        pass
    with pytest.raises(ConfigurationError, match="has not been started"):
        _ = database.engine


def test_partial_storage_startup_releases_storage_and_database() -> None:
    from io import BytesIO

    class FailingStorage(MinioStorage):
        resource = BytesIO()

        async def startup(self) -> None:
            raise RuntimeError("storage startup failed after allocation")

        async def shutdown(self) -> None:
            self.resource.close()
            await super().shutdown()

    settings = Settings(
        _env_file=None,
        app_env="test",
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
    )
    database = DatabaseManager(settings)
    storage = FailingStorage(settings)
    application = create_app(settings=settings, database=database, storage=storage)
    with pytest.raises(RuntimeError, match="storage startup failed"), TestClient(application):
        pass
    assert storage.resource.closed
    with pytest.raises(ConfigurationError, match="has not been started"):
        _ = database.engine


def test_storage_shutdown_error_still_releases_database() -> None:
    class FailingStorage(MinioStorage):
        async def shutdown(self) -> None:
            await super().shutdown()
            raise RuntimeError("storage shutdown failed")

    settings = Settings(
        _env_file=None,
        app_env="test",
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
    )
    database = DatabaseManager(settings)
    application = create_app(settings=settings, database=database, storage=FailingStorage(settings))
    with pytest.raises(RuntimeError, match="storage shutdown failed"), TestClient(application):
        pass
    with pytest.raises(ConfigurationError, match="has not been started"):
        _ = database.engine


def test_transport_shutdown_failure_does_not_leave_other_sessions_open() -> None:
    from app.modules.payments.provider import AiohttpYooKassaTransport
    from app.runtime import build_lifespan

    class FailingTransport(AiohttpYooKassaTransport):
        async def shutdown(self) -> None:
            await super().shutdown()
            raise RuntimeError("transport shutdown failed")

    settings = Settings(
        _env_file=None,
        app_env="test",
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        yookassa_shop_id="local-test",
        yookassa_api_key="local-secret",
    )
    database = DatabaseManager(settings)
    first = AiohttpYooKassaTransport(settings)
    last = FailingTransport(settings)

    async def verified() -> None:
        pass

    application = FastAPI(
        lifespan=build_lifespan(
            settings=settings,
            database=database,
            storage=MinioStorage(settings),
            transports=[first, last],
            verify_startup=verified,
            bank_payout_service=None,
        )
    )
    with pytest.raises(RuntimeError, match="transport shutdown failed"), TestClient(application):
        first_session, last_session = first._session, last._session
    assert first_session.closed and last_session.closed
    with pytest.raises(ConfigurationError, match="has not been started"):
        _ = database.engine


def test_unexpected_background_exit_makes_readiness_fail(monkeypatch, caplog) -> None:
    from app import runtime

    class FailedDirectory:
        def __init__(self, database, settings):
            pass

        async def run(self):
            raise RuntimeError("directory internal error")

    monkeypatch.setattr(runtime, "PickupDirectory", FailedDirectory)
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        cdek_client_id="test-client",
        cdek_client_secret="test-secret",
    )
    application = create_app(settings=settings)

    @application.get("/settle-background")
    async def settle_background():
        await asyncio.sleep(0)
        return {"ok": True}

    with (
        pytest.raises(RuntimeError, match="directory internal error"),
        TestClient(application) as client,
    ):
        client.get("/settle-background")
        readiness_status = client.get("/health/ready").status_code
    assert readiness_status == 503
    assert any(getattr(record, "event", None) == "runtime.task.failed" for record in caplog.records)


def test_factory_exposes_health_without_legacy_fallback() -> None:
    settings = Settings(_env_file=None, app_env="test")
    application = create_app(settings=settings)
    with TestClient(application) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {
            "status": "ready",
            "database": "disabled",
            "storage": "disabled",
        }
        for path in ("/api/products", "/api/settings", "/api/orders", "/admin"):
            assert client.get(path).status_code == 404


def test_factory_leaves_persistent_cart_routes_disabled_by_default() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=False,
        database_url=None,
    )
    application = create_app(settings=settings)
    registered_paths = {route.path for route in iter_route_contexts(application.routes)}

    assert "/api/qr-code" in registered_paths
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
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key=base64.urlsafe_b64encode(b"n" * 32).decode(),
        crm_api_enabled=True,
        crm_writes_enabled=True,
    )
    application = create_app(settings=settings)
    registered_paths = {route.path for route in iter_route_contexts(application.routes)}

    assert "/api/support" in registered_paths
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
        for route in iter_route_contexts(application.routes)
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
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        catalog_reads_enabled=True,
        catalog_writes_enabled=True,
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="http://storage.test",
        identity_api_enabled=True,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key=base64.urlsafe_b64encode(b"n" * 32).decode(),
        carts_v2_enabled=True,
        crm_api_enabled=True,
        crm_writes_enabled=True,
        crm_files_enabled=True,
    )
    application = create_app(settings=settings)
    registered = {
        (method, route.path)
        for route in iter_route_contexts(application.routes)
        for method in getattr(route, "methods", set())
    }

    assert {
        ("POST", "/api/products"),
        ("GET", "/api/product-categories"),
        ("POST", "/api/product-categories"),
        ("PUT", "/api/product-categories/{category_id}"),
        ("PUT", "/api/products/{product_id}"),
        ("DELETE", "/api/products/{product_id}"),
        ("POST", "/api/upload"),
        ("GET", "/api/cart/{cart_id}"),
        ("PUT", "/api/cart/{cart_id}"),
        ("GET", "/api/crm/projects"),
        ("GET", "/api/crm/projects/{project_id}"),
        ("GET", "/api/crm/reference/fabrics"),
        ("GET", "/api/crm/reference/garment-models"),
        ("POST", "/api/crm/reference/fabrics"),
        ("PUT", "/api/crm/reference/fabrics/{fabric_id}"),
        ("POST", "/api/crm/reference/garment-models"),
        ("PUT", "/api/crm/reference/garment-models/{garment_model_id}"),
        ("POST", "/api/crm/reference/garment-models/{garment_model_id}/products"),
        ("POST", "/api/crm/reference/garment-models/{garment_model_id}/tech-cards"),
        ("GET", "/api/crm/assortment/patterns"),
        ("GET", "/api/crm/assortment/products"),
        ("POST", "/api/crm/assortment/patterns"),
        ("GET", "/api/crm/assortment/fabric-requirements"),
        ("POST", "/api/crm/assortment/fabric-requirements"),
        ("GET", "/api/crm/assortment/accessory-categories"),
        ("POST", "/api/crm/assortment/accessory-categories"),
        ("GET", "/api/crm/assortment/accessories"),
        ("POST", "/api/crm/assortment/accessories"),
        ("GET", "/api/crm/assortment/accessory-requirements"),
        ("POST", "/api/crm/assortment/accessory-requirements"),
        ("GET", "/api/crm/assortment/boxes"),
        ("POST", "/api/crm/assortment/boxes"),
        ("GET", "/api/crm/assortment/packaging-rules"),
        ("POST", "/api/crm/assortment/packaging-rules"),
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
        ("GET", "/api/production/admin/assortment/directory/pattern-models"),
        ("GET", "/api/production/admin/assortment/directory/categories/{kind}"),
        ("GET", "/api/production/admin/assortment/model-categories/{category_id}"),
        ("GET", "/api/production/admin/assortment/product-categories/{category_id}"),
        ("POST", "/api/production/admin/assortment/model-categories"),
        ("PUT", "/api/production/admin/assortment/model-categories/{category_id}"),
        ("POST", "/api/production/admin/assortment/models"),
        ("GET", "/api/production/admin/assortment/directory/tech-cards"),
        ("GET", "/api/production/admin/assortment/directory/tech-card-models"),
        ("GET", "/api/production/admin/assortment/tech-cards/{card_id}/revision-source"),
        ("GET", "/api/production/admin/assortment/directory/models"),
        ("GET", "/api/production/admin/assortment/directory/fabrics"),
        ("GET", "/api/production/admin/assortment/directory/fabric-requirements"),
        ("GET", "/api/production/admin/assortment/directory/selected"),
        ("GET", "/api/production/admin/assortment/models/{model_id}"),
        ("POST", "/api/production/admin/assortment/fabrics"),
        ("PUT", "/api/production/admin/assortment/fabrics/{fabric_id}"),
        ("POST", "/api/production/admin/assortment/fabric-requirements"),
        ("PUT", "/api/production/admin/assortment/fabric-requirements/{requirement_id}"),
        ("GET", "/api/production/admin/assortment/directory/patterns"),
        ("GET", "/api/production/admin/assortment/directory/pattern-sizes"),
        ("GET", "/api/production/admin/assortment/models/{model_id}/pattern-coverage"),
        ("GET", "/api/production/admin/assortment/models/{model_id}/pattern-size/{size_id}"),
        ("GET", "/api/production/admin/assortment/patterns/{pattern_id}"),
        ("GET", "/api/production/admin/assortment/directory/accessories"),
        ("GET", "/api/production/admin/assortment/directory/boxes"),
        ("GET", "/api/production/admin/assortment/directory/accessory-categories"),
        ("GET", "/api/production/admin/assortment/directory/accessory-requirements"),
        ("GET", "/api/production/admin/assortment/directory/packaging-rules"),
        ("GET", "/api/production/admin/assortment/products"),
        ("GET", "/api/production/admin/assortment/product-communities"),
        ("POST", "/api/production/admin/assortment/media/public"),
        ("POST", "/api/production/admin/assortment/media/pattern"),
    } <= registered
    for name in [
        "accessories",
        "boxes",
        "accessory-categories",
        "accessory-requirements",
        "packaging-rules",
        "tech-cards",
        "patterns",
        "models",
        "model-categories",
        "product-categories",
    ]:
        assert ("GET", f"/api/production/admin/assortment/{name}") not in registered
    assert ("GET", "/api/production/admin/assortment/fabrics") not in registered
    assert ("GET", "/api/production/admin/assortment/fabric-requirements") not in registered
    assert not any(path in {"/admin", "/admin/{path:path}"} for _method, path in registered)
    # Removed surfaces are ordinary unmatched routes, independent of rollout flags.
    client = TestClient(application)
    try:
        for method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"):
            for path in ("/admin", "/admin/editor", "/admin/models", "/admin/settings"):
                assert client.request(method, path).status_code == 404
    finally:
        client.close()


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
        "storage": "disabled",
    }


def test_readiness_returns_503_when_database_loses_connectivity() -> None:
    class UnavailableDatabase(DatabaseManager):
        async def ping(self) -> bool:
            return False

    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
    )
    database = UnavailableDatabase(settings)
    application = create_app(settings=settings, database=database)

    with TestClient(application) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "sqlite",
        "storage": "disabled",
    }


def test_readiness_checks_enabled_minio_buckets() -> None:
    class AvailableClient:
        def bucket_exists(self, bucket_name: str) -> bool:
            return bucket_name in {
                "garment-buro-test-media",
                "garment-buro-test-crm-private",
                "garment-buro-test-projects",
            }

        def get_bucket_policy(self, bucket_name: str) -> str:
            return ""

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
        "database": "disabled",
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
        "database": "disabled",
        "storage": "minio",
    }
