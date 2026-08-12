from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError


def production_settings(**overrides) -> Settings:
    values = {
        "app_env": AppEnvironment.PRODUCTION,
        "jwt_secret": "j" * 32,
        "cdek_client_id": "cdek-client",
        "cdek_client_secret": "cdek-secret",
        "yookassa_shop_id": "shop-id",
        "yookassa_api_key": "payment-secret",
        "smtp_password": "smtp-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_local_settings_keep_current_runtime_defaults() -> None:
    settings = Settings(_env_file=None, app_env=AppEnvironment.LOCAL)

    assert settings.legacy_database_url == "sqlite:///./ecommerce.db"
    assert settings.database_url is None
    assert not settings.database_enabled
    assert not settings.catalog_reads_enabled
    assert not settings.catalog_writes_enabled
    assert not settings.carts_v2_enabled
    assert not settings.minio_enabled
    assert settings.minio_media_bucket == "garment-buro-local-media"
    assert settings.minio_crm_bucket == "garment-buro-local-crm-private"
    assert settings.products_cache_ttl_seconds == 3_600
    assert settings.product_cache_ttl_seconds == 3_600
    assert settings.cart_cache_ttl_seconds == 2_592_000
    assert settings.inventory_reservation_ttl_seconds == 1_800
    assert settings.order_guest_access_ttl_days == 30
    assert settings.yookassa_api_url == "https://api.yookassa.ru/v3"
    assert settings.yookassa_timeout_seconds == 10
    assert not settings.payment_creation_enabled
    assert not settings.checkout_v2_enabled
    assert not settings.crm_api_enabled
    assert not settings.crm_writes_enabled
    assert not settings.crm_files_enabled
    assert settings.crm_file_max_upload_bytes == 26_214_400
    assert settings.payment_creation_retry_window_seconds == 82_800
    assert settings.payment_max_attempts_per_order == 3
    assert not settings.fulfillment_outbox_enabled
    assert not settings.fulfillment_email_enabled
    assert not settings.fulfillment_cdek_enabled
    assert not settings.fulfillment_crm_enabled
    assert not settings.cdek_quote_enabled
    assert not settings.cdek_creation_enabled
    assert settings.cdek_timeout_seconds == 15
    assert settings.cdek_processing_timeout_seconds == 120
    assert settings.fulfillment_max_attempts == 5
    assert settings.fulfillment_retry_base_seconds == 30
    assert settings.fulfillment_retry_cap_seconds == 1_800
    assert settings.fulfillment_processing_timeout_seconds == 300
    assert settings.fulfillment_poll_seconds == 5
    assert settings.yookassa_receipt_product_vat_code is None
    assert not settings.payment_webhook_v2_enabled
    assert settings.payment_webhook_trusted_proxy_networks == ()
    assert settings.payment_event_max_attempts == 5
    assert settings.payment_event_retry_cap_seconds == 1_800
    assert settings.payment_event_poll_seconds == 5
    assert not settings.payment_reconciliation_enabled
    assert settings.payment_reconciliation_max_attempts == 288
    assert settings.payment_reconciliation_interval_seconds == 300
    assert not settings.order_reads_enabled
    assert settings.jwt_access_expire_minutes == 43_200
    assert settings.identity_otp_digits == 4
    assert settings.identity_access_expire_minutes == 15
    assert settings.identity_refresh_expire_days == 30
    assert not settings.identity_api_enabled
    assert settings.identity_refresh_cookie_name == "gb_refresh"
    assert settings.notification_max_attempts == 5
    assert settings.notification_retry_cap_seconds == 3_600
    assert "*" not in settings.cors_origin_list
    assert "https://garment-buro.ru" in settings.cors_origin_list


def test_inventory_reservation_ttl_is_bounded() -> None:
    with pytest.raises(ValidationError, match="INVENTORY_RESERVATION_TTL_SECONDS"):
        Settings(_env_file=None, inventory_reservation_ttl_seconds=59)
    with pytest.raises(ValidationError, match="INVENTORY_RESERVATION_TTL_SECONDS"):
        Settings(_env_file=None, inventory_reservation_ttl_seconds=86_401)


def test_order_reads_require_identity_database_and_reviewed_fingerprint() -> None:
    with pytest.raises(ValidationError, match="DATABASE_ENABLED"):
        Settings(_env_file=None, order_reads_enabled=True)
    with pytest.raises(ValidationError, match="IDENTITY_API_ENABLED"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            order_reads_enabled=True,
        )
    with pytest.raises(ValidationError, match="ORDER_MIGRATION_FINGERPRINT"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            identity_api_enabled=True,
            order_reads_enabled=True,
        )


def test_crm_api_requires_target_database_and_identity() -> None:
    with pytest.raises(ValidationError, match="DATABASE_ENABLED"):
        Settings(_env_file=None, crm_api_enabled=True)
    with pytest.raises(ValidationError, match="IDENTITY_API_ENABLED"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            crm_api_enabled=True,
        )
    with pytest.raises(ValidationError, match="CRM_API_ENABLED"):
        Settings(_env_file=None, crm_writes_enabled=True)
    with pytest.raises(ValidationError, match="CRM_WRITES_ENABLED"):
        Settings(_env_file=None, crm_files_enabled=True)
    with pytest.raises(ValidationError, match="MINIO_ENABLED"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            identity_api_enabled=True,
            crm_api_enabled=True,
            crm_writes_enabled=True,
            crm_files_enabled=True,
        )


def test_crm_file_upload_limit_is_positive_and_bounded_by_storage_limit() -> None:
    with pytest.raises(ValidationError, match="CRM_FILE_MAX_UPLOAD_BYTES"):
        Settings(_env_file=None, crm_file_max_upload_bytes=0)
    with pytest.raises(ValidationError, match="CRM_FILE_MAX_UPLOAD_BYTES"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            identity_api_enabled=True,
            crm_api_enabled=True,
            crm_writes_enabled=True,
            crm_files_enabled=True,
            minio_enabled=True,
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_public_base_url="https://storage.test",
            media_max_upload_bytes=100,
            crm_file_max_upload_bytes=101,
        )


def test_order_guest_access_ttl_is_bounded() -> None:
    with pytest.raises(ValidationError, match="ORDER_GUEST_ACCESS_TTL_DAYS"):
        Settings(_env_file=None, order_guest_access_ttl_days=0)
    with pytest.raises(ValidationError, match="ORDER_GUEST_ACCESS_TTL_DAYS"):
        Settings(_env_file=None, order_guest_access_ttl_days=366)


def test_cors_origins_are_normalized_and_deduplicated() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins="https://example.test/, https://example.test,http://localhost:3000/",
    )

    assert settings.cors_origin_list == [
        "https://example.test",
        "http://localhost:3000",
    ]


def test_wildcard_cors_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not contain"):
        Settings(_env_file=None, cors_origins="*")


def test_enabled_database_requires_async_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL is required"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url=None,
        )


def test_catalog_read_cutover_requires_async_database() -> None:
    with pytest.raises(ValidationError, match="CATALOG_READS_ENABLED"):
        Settings(
            _env_file=None,
            database_enabled=False,
            catalog_reads_enabled=True,
            minio_enabled=True,
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_public_base_url="http://storage.test",
        )

    with pytest.raises(ValidationError, match="MINIO_ENABLED"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            catalog_reads_enabled=True,
            minio_enabled=False,
        )

    with pytest.raises(ValidationError, match="CATALOG_MIGRATION_FINGERPRINT"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            catalog_reads_enabled=True,
            minio_enabled=True,
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_public_base_url="http://storage.test",
            catalog_migration_fingerprint=None,
        )


def test_catalog_write_cutover_requires_reads_and_identity() -> None:
    with pytest.raises(ValidationError, match="CATALOG_READS_ENABLED"):
        Settings(_env_file=None, catalog_writes_enabled=True)

    with pytest.raises(ValidationError, match="IDENTITY_API_ENABLED"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            catalog_reads_enabled=True,
            catalog_writes_enabled=True,
            catalog_migration_fingerprint="c" * 64,
            minio_enabled=True,
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_public_base_url="http://storage.test",
        )


def test_cart_cutover_requires_database_and_reviewed_migration() -> None:
    with pytest.raises(ValidationError, match="DATABASE_ENABLED"):
        Settings(_env_file=None, carts_v2_enabled=True)
    with pytest.raises(ValidationError, match="CARTS_MIGRATION_FINGERPRINT"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            carts_v2_enabled=True,
        )
    settings = Settings(
        _env_file=None,
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        carts_v2_enabled=True,
        carts_migration_fingerprint="a" * 64,
    )
    assert settings.carts_v2_enabled

    with pytest.raises(ValidationError, match="CATALOG_CONTENT_MIGRATION_FINGERPRINT"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            catalog_reads_enabled=True,
            catalog_writes_enabled=True,
            catalog_migration_fingerprint="c" * 64,
            minio_enabled=True,
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_public_base_url="http://storage.test",
            identity_api_enabled=True,
            identity_migration_fingerprint="d" * 64,
            jwt_secret="j" * 32,
            identity_otp_pepper="p" * 32,
            notification_encryption_key="bm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm4=",
        )


def test_enabled_minio_requires_credentials_and_public_url() -> None:
    with pytest.raises(ValidationError, match="Missing required MinIO settings"):
        Settings(
            _env_file=None,
            minio_enabled=True,
            minio_access_key=None,
            minio_secret_key=None,
            minio_public_base_url=None,
        )


def test_minio_endpoint_and_bucket_prefix_are_validated() -> None:
    with pytest.raises(ValidationError, match="without a URL scheme"):
        Settings(
            _env_file=None,
            minio_enabled=True,
            minio_endpoint="http://localhost:9000",
            minio_access_key="local-access",
            minio_secret_key="local-secret",
            minio_public_base_url="http://localhost:9000",
        )

    with pytest.raises(ValidationError, match=r"only host\[:port\]"):
        Settings(
            _env_file=None,
            minio_enabled=True,
            minio_endpoint="localhost:9000/path",
            minio_access_key="local-access",
            minio_secret_key="local-secret",
            minio_public_base_url="http://localhost:9000",
        )

    with pytest.raises(ValidationError, match="MINIO_BUCKET_PREFIX"):
        Settings(_env_file=None, minio_bucket_prefix="Invalid_Prefix")

    with pytest.raises(ValidationError, match="absolute HTTP"):
        Settings(
            _env_file=None,
            minio_enabled=True,
            minio_access_key="local-access",
            minio_secret_key="local-secret",
            minio_public_base_url="storage.local",
        )


def test_minio_bucket_is_isolated_by_environment() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.STAGING,
        minio_bucket_prefix="garment-buro",
        **{
            "jwt_secret": "j" * 32,
            "cdek_client_id": "cdek-client",
            "cdek_client_secret": "cdek-secret",
            "yookassa_shop_id": "shop-id",
            "yookassa_api_key": "payment-secret",
            "smtp_password": "smtp-secret",
        },
    )

    assert settings.minio_media_bucket == "garment-buro-staging-media"
    assert settings.minio_crm_bucket == "garment-buro-staging-crm-private"


def test_production_requires_all_external_service_secrets() -> None:
    with pytest.raises(ValidationError) as error:
        production_settings(
            jwt_secret="",
            cdek_client_id="",
            cdek_client_secret="",
            yookassa_shop_id="",
            yookassa_api_key="",
            smtp_password="",
        )

    message = str(error.value)
    for setting_name in (
        "JWT_SECRET",
        "CDEK_CLIENT_ID",
        "CDEK_CLIENT_SECRET",
        "YOOKASSA_SHOP_ID",
        "YOOKASSA_API_KEY",
        "SMTP_PASSWORD",
    ):
        assert setting_name in message


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        production_settings(jwt_secret="too-short")


def test_identity_policy_settings_reject_unsafe_ranges() -> None:
    with pytest.raises(ValidationError, match="IDENTITY_OTP_DIGITS"):
        Settings(_env_file=None, identity_otp_digits=3)
    with pytest.raises(ValidationError, match="IDENTITY_OTP_MAX_ATTEMPTS"):
        Settings(_env_file=None, identity_otp_max_attempts=11)
    with pytest.raises(ValidationError, match="Identity settings must be positive"):
        Settings(_env_file=None, identity_access_expire_minutes=0)


def test_identity_api_cutover_requires_reviewed_data_and_independent_secrets() -> None:
    assert (
        Settings(
            _env_file=None,
            identity_legacy_token_grace_until="",
        ).identity_legacy_token_grace_until
        is None
    )
    common = {
        "_env_file": None,
        "app_env": AppEnvironment.TEST,
        "identity_api_enabled": True,
        "database_enabled": True,
        "database_url": "sqlite+aiosqlite:///:memory:",
        "identity_migration_fingerprint": "f" * 64,
        "jwt_secret": "j" * 32,
        "identity_otp_pepper": "p" * 32,
        "notification_encryption_key": "invalid-but-present",
    }
    for missing_field, expected_name in (
        ("identity_migration_fingerprint", "IDENTITY_MIGRATION_FINGERPRINT"),
        ("jwt_secret", "JWT_SECRET"),
        ("identity_otp_pepper", "IDENTITY_OTP_PEPPER"),
        ("notification_encryption_key", "NOTIFICATION_ENCRYPTION_KEY"),
    ):
        values = dict(common)
        values[missing_field] = None
        with pytest.raises(ValidationError, match=expected_name):
            Settings(**values)

    with pytest.raises(ValidationError, match="current frontend"):
        Settings(**{**common, "identity_otp_digits": 6})
    with pytest.raises(ValidationError, match="must include a timezone"):
        Settings(
            _env_file=None,
            identity_legacy_token_grace_until="2026-09-01T00:00:00",
        )
    with pytest.raises(ValidationError, match="within 31 days"):
        Settings(
            _env_file=None,
            identity_legacy_token_grace_until="2099-01-01T00:00:00+00:00",
        )


def test_notification_policy_settings_reject_unsafe_ranges() -> None:
    with pytest.raises(ValidationError, match="NOTIFICATION_MAX_ATTEMPTS"):
        Settings(_env_file=None, notification_max_attempts=21)
    with pytest.raises(ValidationError, match="Notification settings must be positive"):
        Settings(_env_file=None, notification_poll_seconds=0)
    with pytest.raises(ValidationError, match="NOTIFICATION_RETRY_CAP_SECONDS"):
        Settings(
            _env_file=None,
            notification_retry_base_seconds=60,
            notification_retry_cap_seconds=30,
        )


def test_cdek_foundation_settings_reject_unsafe_values() -> None:
    with pytest.raises(ValidationError, match="CDEK_API_URL"):
        Settings(_env_file=None, cdek_api_url="http://api.cdek.ru/v2")
    with pytest.raises(ValidationError, match="outside local/test"):
        production_settings(cdek_api_url="https://cdek.example.test/v2")
    with pytest.raises(ValidationError, match="CDEK_REQUEST_ENCRYPTION_KEY_VERSION"):
        Settings(_env_file=None, cdek_request_encryption_key_version=0)
    with pytest.raises(ValidationError, match="CDEK_SENDER_NAME"):
        Settings(_env_file=None, cdek_sender_name=" ")
    with pytest.raises(ValidationError, match="CDEK settings must be positive"):
        Settings(_env_file=None, cdek_sender_city_code=0)
    with pytest.raises(ValidationError, match="CDEK_MAX_PACKAGES"):
        Settings(_env_file=None, cdek_max_packages=0)
    with pytest.raises(ValidationError, match="CDEK_CREATION_MAX_ATTEMPTS"):
        Settings(_env_file=None, cdek_creation_max_attempts=21)
    with pytest.raises(ValidationError, match="CDEK_TIMEOUT_SECONDS"):
        Settings(_env_file=None, cdek_timeout_seconds=61)
    with pytest.raises(ValidationError, match="CDEK worker settings must be positive"):
        Settings(_env_file=None, cdek_poll_seconds=0)
    with pytest.raises(ValidationError, match="CDEK_RETRY_CAP_SECONDS"):
        Settings(
            _env_file=None,
            cdek_retry_base_seconds=60,
            cdek_retry_cap_seconds=30,
        )
    with pytest.raises(ValidationError, match="CDEK_PROCESSING_TIMEOUT_SECONDS"):
        Settings(
            _env_file=None,
            cdek_timeout_seconds=15,
            cdek_processing_timeout_seconds=15,
        )
    with pytest.raises(ValidationError, match="FULFILLMENT_OUTBOX_ENABLED"):
        Settings(_env_file=None, fulfillment_cdek_enabled=True)
    with pytest.raises(ValidationError, match="FULFILLMENT_CDEK_ENABLED"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            fulfillment_outbox_enabled=True,
            cdek_creation_enabled=True,
        )
    with pytest.raises(ValidationError, match="Target CDEK quote"):
        Settings(
            _env_file=None,
            cdek_quote_enabled=True,
            cdek_client_id="cdek-client",
            cdek_client_secret="cdek-secret",
        )
    with pytest.raises(ValidationError, match="Missing required CDEK quote settings"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            catalog_reads_enabled=True,
            catalog_migration_fingerprint="a" * 64,
            minio_enabled=True,
            minio_access_key="access",
            minio_secret_key="secret",
            minio_public_base_url="https://cdn.example.test",
            cdek_quote_enabled=True,
            cdek_client_id=None,
            cdek_client_secret=None,
        )

    enabled = Settings(
        _env_file=None,
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        fulfillment_outbox_enabled=True,
        fulfillment_cdek_enabled=True,
        cdek_creation_enabled=True,
        cdek_client_id="cdek-client",
        cdek_client_secret="cdek-secret",
        cdek_request_encryption_key="Y2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2M=",
    )
    assert enabled.cdek_creation_enabled

    quote_enabled = Settings(
        _env_file=None,
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        catalog_reads_enabled=True,
        catalog_migration_fingerprint="a" * 64,
        minio_enabled=True,
        minio_access_key="access",
        minio_secret_key="secret",
        minio_public_base_url="https://cdn.example.test",
        cdek_quote_enabled=True,
        cdek_client_id="cdek-client",
        cdek_client_secret="cdek-secret",
    )
    assert quote_enabled.cdek_quote_enabled


def test_payment_provider_policy_settings_reject_unsafe_values() -> None:
    with pytest.raises(ValidationError, match="YOOKASSA_API_URL"):
        Settings(_env_file=None, yookassa_api_url="http://api.yookassa.ru/v3")
    with pytest.raises(ValidationError, match="YOOKASSA_TIMEOUT_SECONDS"):
        Settings(_env_file=None, yookassa_timeout_seconds=61)
    with pytest.raises(ValidationError, match="PAYMENT_EVENT_MAX_ATTEMPTS"):
        Settings(_env_file=None, payment_event_max_attempts=21)
    with pytest.raises(ValidationError, match="Payment event settings must be positive"):
        Settings(_env_file=None, payment_event_poll_seconds=0)
    with pytest.raises(ValidationError, match="PAYMENT_EVENT_RETRY_CAP_SECONDS"):
        Settings(
            _env_file=None,
            payment_event_retry_base_seconds=60,
            payment_event_retry_cap_seconds=30,
        )
    with pytest.raises(ValidationError, match="must exceed"):
        Settings(
            _env_file=None,
            yookassa_timeout_seconds=10,
            payment_event_processing_timeout_seconds=10,
        )
    with pytest.raises(ValidationError, match="outside local/test"):
        production_settings(yookassa_api_url="https://payments.example.test/v3")
    with pytest.raises(ValidationError, match="PAYMENT_WEBHOOK_V2_ENABLED"):
        Settings(_env_file=None, payment_webhook_v2_enabled=True)
    with pytest.raises(ValidationError, match="PAYMENT_WEBHOOK_TRUSTED_PROXY_CIDRS"):
        Settings(_env_file=None, payment_webhook_trusted_proxy_cidrs="not-a-network")
    with pytest.raises(ValidationError, match="entire IP family"):
        Settings(_env_file=None, payment_webhook_trusted_proxy_cidrs="0.0.0.0/0")

    guarded = Settings(
        _env_file=None,
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        payment_webhook_v2_enabled=True,
        payment_webhook_trusted_proxy_cidrs="10.0.0.0/8,2001:db8::/32",
    )
    assert tuple(str(value) for value in guarded.payment_webhook_trusted_proxy_networks) == (
        "10.0.0.0/8",
        "2001:db8::/32",
    )
    with pytest.raises(ValidationError, match="PAYMENT_RECONCILIATION_ENABLED"):
        Settings(_env_file=None, payment_reconciliation_enabled=True)
    with pytest.raises(ValidationError, match="reconciliation settings"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            payment_reconciliation_enabled=True,
            yookassa_shop_id="",
            yookassa_api_key="",
        )
    with pytest.raises(ValidationError, match="MAX_ATTEMPTS"):
        Settings(_env_file=None, payment_reconciliation_max_attempts=1_001)
    with pytest.raises(ValidationError, match="settings must be positive"):
        Settings(_env_file=None, payment_reconciliation_interval_seconds=0)
    with pytest.raises(ValidationError, match="RETRY_CAP_SECONDS"):
        Settings(
            _env_file=None,
            payment_reconciliation_retry_base_seconds=60,
            payment_reconciliation_retry_cap_seconds=30,
        )
    with pytest.raises(ValidationError, match="PROCESSING_TIMEOUT_SECONDS"):
        Settings(
            _env_file=None,
            yookassa_timeout_seconds=10,
            payment_reconciliation_processing_timeout_seconds=10,
        )

    reconciliation = Settings(
        _env_file=None,
        database_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        payment_reconciliation_enabled=True,
        yookassa_shop_id="test-shop",
        yookassa_api_key="test-key",
    )
    assert reconciliation.payment_reconciliation_enabled


def test_payment_creation_requires_explicit_fiscal_contract() -> None:
    base = {
        "_env_file": None,
        "app_env": AppEnvironment.TEST,
        "database_enabled": True,
        "database_url": "sqlite+aiosqlite:///:memory:",
        "yookassa_shop_id": "test-shop",
        "yookassa_api_key": "test-key",
        "payment_creation_enabled": True,
    }
    with pytest.raises(ValidationError, match="payment creation settings") as missing:
        Settings(**base)
    for setting_name in (
        "YOOKASSA_RECEIPT_PRODUCT_VAT_CODE",
        "YOOKASSA_RECEIPT_DELIVERY_VAT_CODE",
        "YOOKASSA_RECEIPT_PRODUCT_PAYMENT_MODE",
        "YOOKASSA_RECEIPT_DELIVERY_PAYMENT_MODE",
        "YOOKASSA_RECEIPT_PRODUCT_SUBJECT",
        "YOOKASSA_RECEIPT_DELIVERY_SUBJECT",
    ):
        assert setting_name in str(missing.value)

    configured = Settings(
        **base,
        yookassa_receipt_tax_system_code=1,
        yookassa_receipt_product_vat_code=1,
        yookassa_receipt_delivery_vat_code=1,
        yookassa_receipt_product_payment_mode="full_payment",
        yookassa_receipt_delivery_payment_mode="full_payment",
        yookassa_receipt_product_subject="non_marked",
        yookassa_receipt_delivery_subject="service",
    )
    assert configured.payment_creation_enabled

    with pytest.raises(ValidationError, match="marking-code implementation"):
        Settings(
            **base,
            yookassa_receipt_product_subject="marked",
        )
    with pytest.raises(ValidationError, match="VAT codes"):
        Settings(
            _env_file=None,
            yookassa_receipt_product_vat_code=13,
        )
    with pytest.raises(ValidationError, match="must exceed"):
        Settings(
            _env_file=None,
            yookassa_timeout_seconds=10,
            payment_creation_processing_timeout_seconds=10,
        )

    empty = Settings(
        _env_file=None,
        yookassa_receipt_tax_system_code="",
        yookassa_receipt_product_vat_code="",
        yookassa_receipt_product_payment_mode="",
    )
    assert empty.yookassa_receipt_tax_system_code is None
    assert empty.yookassa_receipt_product_vat_code is None
    assert empty.yookassa_receipt_product_payment_mode is None

    with pytest.raises(ValidationError, match="PAYMENT_MAX_ATTEMPTS_PER_ORDER"):
        Settings(_env_file=None, payment_max_attempts_per_order=0)
    with pytest.raises(ValidationError, match="PAYMENT_MAX_ATTEMPTS_PER_ORDER"):
        Settings(_env_file=None, payment_max_attempts_per_order=11)


def test_target_checkout_requires_all_owned_domain_boundaries() -> None:
    with pytest.raises(ValidationError, match="Target checkout") as missing:
        Settings(_env_file=None, checkout_v2_enabled=True)

    message = str(missing.value)
    for setting_name in (
        "CATALOG_READS_ENABLED",
        "IDENTITY_API_ENABLED",
        "ORDER_READS_ENABLED",
        "PAYMENT_CREATION_ENABLED",
    ):
        assert setting_name in message


def test_fulfillment_outbox_is_bounded_and_requires_database() -> None:
    with pytest.raises(ValidationError, match="FULFILLMENT_MAX_ATTEMPTS"):
        Settings(_env_file=None, fulfillment_max_attempts=0)
    with pytest.raises(ValidationError, match="FULFILLMENT_MAX_ATTEMPTS"):
        Settings(_env_file=None, fulfillment_max_attempts=21)
    with pytest.raises(ValidationError, match="DATABASE_ENABLED"):
        Settings(_env_file=None, fulfillment_outbox_enabled=True)
    with pytest.raises(ValidationError, match="FULFILLMENT_OUTBOX_ENABLED"):
        Settings(
            _env_file=None,
            fulfillment_email_enabled=True,
            notification_encryption_key=("ZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmY="),
        )
    with pytest.raises(ValidationError, match="NOTIFICATION_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
            fulfillment_outbox_enabled=True,
            fulfillment_email_enabled=True,
        )
    with pytest.raises(ValidationError, match="FULFILLMENT_OUTBOX_ENABLED"):
        Settings(_env_file=None, fulfillment_crm_enabled=True)
    with pytest.raises(ValidationError, match="Fulfillment settings"):
        Settings(_env_file=None, fulfillment_poll_seconds=0)
    with pytest.raises(ValidationError, match="greater than or equal"):
        Settings(
            _env_file=None,
            fulfillment_retry_base_seconds=60,
            fulfillment_retry_cap_seconds=30,
        )


def test_secret_values_are_masked_in_settings_repr() -> None:
    settings = production_settings()

    rendered = repr(settings)
    assert "payment-secret" not in rendered
    assert "smtp-secret" not in rendered
    assert "**********" in rendered


def test_missing_optional_secret_fails_only_when_requested() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        jwt_secret=None,
    )

    with pytest.raises(ConfigurationError, match="JWT_SECRET is not configured"):
        settings.require_secret("jwt_secret", "JWT_SECRET")


def test_environment_example_does_not_ship_secret_values() -> None:
    env_example = Path(__file__).resolve().parents[3] / ".env.example"
    values = {
        key: value
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
        for key, value in [line.split("=", 1)]
    }

    for secret_name in (
        "JWT_SECRET",
        "CDEK_CLIENT_ID",
        "CDEK_CLIENT_SECRET",
        "CDEK_REQUEST_ENCRYPTION_KEY",
        "CDEK_PREVIOUS_REQUEST_ENCRYPTION_KEYS",
        "YOOKASSA_SHOP_ID",
        "YOOKASSA_API_KEY",
        "SMTP_PASSWORD",
        "POSTGRES_PASSWORD",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "IDENTITY_OTP_PEPPER",
        "NOTIFICATION_ENCRYPTION_KEY",
        "NOTIFICATION_PREVIOUS_ENCRYPTION_KEYS",
    ):
        assert values[secret_name] == ""
