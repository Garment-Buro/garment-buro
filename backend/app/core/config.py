from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .exceptions import ConfigurationError

YOOKASSA_RECEIPT_PAYMENT_MODES = {
    "full_prepayment",
    "partial_prepayment",
    "advance",
    "full_payment",
    "partial_payment",
    "credit",
    "credit_payment",
}
YOOKASSA_RECEIPT_PRODUCT_SUBJECTS = {"commodity", "non_marked"}
YOOKASSA_RECEIPT_DELIVERY_SUBJECTS = {"service"}


class AppEnvironment(str, Enum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Single source of runtime configuration for legacy and refactored code."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: AppEnvironment = AppEnvironment.LOCAL
    app_name: str = "Garment Buro API"
    public_base_url: str = "https://garment-buro.ru"

    legacy_database_url: str = "sqlite:///./ecommerce.db"
    database_enabled: bool = False
    database_url: str | None = None
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20
    catalog_reads_enabled: bool = False
    catalog_writes_enabled: bool = False
    catalog_migration_fingerprint: str | None = None
    catalog_content_migration_fingerprint: str | None = None
    carts_v2_enabled: bool = False
    carts_migration_fingerprint: str | None = None
    order_reads_enabled: bool = False
    order_migration_fingerprint: str | None = None
    checkout_v2_enabled: bool = False
    partner_program_enabled: bool = False
    partner_attribution_secret: SecretStr | None = None
    partner_attribution_days: int = 30
    partner_commission_hold_days: int = 14
    partner_attribution_cookie_name: str = "gb_partner"
    partner_visitor_cookie_name: str = "gb_partner_visitor"
    partner_cookie_domain: str | None = None
    crm_api_enabled: bool = False
    crm_writes_enabled: bool = False
    crm_files_enabled: bool = False

    minio_enabled: bool = False
    minio_endpoint: str = "localhost:9000"
    minio_access_key: SecretStr | None = None
    minio_secret_key: SecretStr | None = None
    minio_secure: bool = False
    minio_bucket_prefix: str = "garment-buro"
    minio_public_base_url: str | None = None
    minio_presigned_expire_seconds: int = 900
    media_max_upload_bytes: int = 104_857_600
    crm_file_max_upload_bytes: int = 26_214_400

    redis_url: str = "redis://localhost:6379/0"
    products_cache_ttl_seconds: int = 3_600
    product_cache_ttl_seconds: int = 3_600
    cart_cache_ttl_seconds: int = 2_592_000
    inventory_reservation_ttl_seconds: int = 1_800
    order_guest_access_ttl_days: int = 30

    jwt_secret: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 43_200
    identity_otp_pepper: SecretStr | None = None
    identity_otp_digits: int = 4
    identity_otp_expire_minutes: int = 10
    identity_otp_resend_seconds: int = 60
    identity_otp_hourly_limit: int = 5
    identity_otp_max_attempts: int = 5
    identity_access_expire_minutes: int = 15
    identity_refresh_expire_days: int = 30
    identity_max_active_sessions: int = 10
    identity_api_enabled: bool = False
    identity_migration_fingerprint: str | None = None
    identity_legacy_token_grace_until: datetime | None = None
    identity_refresh_cookie_name: str = "gb_refresh"

    notification_encryption_key: SecretStr | None = None
    notification_previous_encryption_keys: SecretStr | None = None
    notification_encryption_key_version: int = 1
    notification_max_attempts: int = 5
    notification_retry_base_seconds: int = 60
    notification_retry_cap_seconds: int = 3_600
    notification_processing_timeout_seconds: int = 300
    notification_poll_seconds: int = 5

    cors_origins: str = (
        "https://garment-buro.ru,"
        "https://www.garment-buro.ru,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
    )

    cdek_api_url: str = "https://api.cdek.ru/v2"
    cdek_client_id: SecretStr | None = None
    cdek_client_secret: SecretStr | None = None
    cdek_request_encryption_key: SecretStr | None = None
    cdek_previous_request_encryption_keys: SecretStr | None = None
    cdek_request_encryption_key_version: int = 1
    cdek_sender_name: str = "GARMENT BURO"
    cdek_sender_city_code: int = 245
    cdek_pickup_point_code: str = "TVR8"
    cdek_warehouse_to_warehouse_tariff: int = 136
    cdek_warehouse_to_door_tariff: int = 137
    cdek_max_packages: int = 100
    fulfillment_cdek_enabled: bool = False
    cdek_quote_enabled: bool = False
    cdek_creation_enabled: bool = False
    cdek_creation_max_attempts: int = 5
    cdek_timeout_seconds: int = 15
    cdek_retry_base_seconds: int = 30
    cdek_retry_cap_seconds: int = 1_800
    cdek_processing_timeout_seconds: int = 120
    cdek_poll_seconds: int = 5

    yookassa_shop_id: SecretStr | None = None
    yookassa_api_key: SecretStr | None = None
    yookassa_api_url: str = "https://api.yookassa.ru/v3"
    yookassa_timeout_seconds: int = 10
    yookassa_webhook_url: str | None = None
    payment_creation_enabled: bool = False
    payment_creation_retry_window_seconds: int = 82_800
    payment_creation_processing_timeout_seconds: int = 60
    payment_management_enabled: bool = False
    payment_operation_processing_timeout_seconds: int = 60
    payment_max_attempts_per_order: int = 3
    yookassa_payout_agent_id: SecretStr | None = None
    yookassa_payout_api_key: SecretStr | None = None
    yookassa_payouts_enabled: bool = False
    payout_retry_window_seconds: int = 82_800
    payout_processing_timeout_seconds: int = 60
    fulfillment_outbox_enabled: bool = False
    fulfillment_email_enabled: bool = False
    fulfillment_crm_enabled: bool = False
    fulfillment_max_attempts: int = 5
    fulfillment_retry_base_seconds: int = 30
    fulfillment_retry_cap_seconds: int = 1_800
    fulfillment_processing_timeout_seconds: int = 300
    fulfillment_poll_seconds: int = 5
    yookassa_receipt_tax_system_code: int | None = None
    yookassa_receipt_product_vat_code: int | None = None
    yookassa_receipt_delivery_vat_code: int | None = None
    yookassa_receipt_product_payment_mode: str | None = None
    yookassa_receipt_delivery_payment_mode: str | None = None
    yookassa_receipt_product_subject: str | None = None
    yookassa_receipt_delivery_subject: str | None = None
    payment_webhook_v2_enabled: bool = False
    payment_webhook_trusted_proxy_cidrs: str = ""
    payment_event_max_attempts: int = 5
    payment_event_retry_base_seconds: int = 30
    payment_event_retry_cap_seconds: int = 1_800
    payment_event_processing_timeout_seconds: int = 300
    payment_event_poll_seconds: int = 5
    payment_reconciliation_enabled: bool = False
    payment_reconciliation_max_attempts: int = 288
    payment_reconciliation_interval_seconds: int = 300
    payment_reconciliation_retry_base_seconds: int = 30
    payment_reconciliation_retry_cap_seconds: int = 1_800
    payment_reconciliation_processing_timeout_seconds: int = 300
    payment_reconciliation_poll_seconds: int = 5

    smtp_server: str = "mail.hosting.reg.ru"
    smtp_port: int = 465
    smtp_user: str = "noreply@garment-buro.ru"
    smtp_password: SecretStr | None = None
    smtp_use_ssl: bool = True

    @field_validator("identity_legacy_token_grace_until", mode="before")
    @classmethod
    def empty_datetime_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("partner_cookie_domain", mode="before")
    @classmethod
    def empty_partner_cookie_domain_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator(
        "yookassa_receipt_tax_system_code",
        "yookassa_receipt_product_vat_code",
        "yookassa_receipt_delivery_vat_code",
        "yookassa_receipt_product_payment_mode",
        "yookassa_receipt_delivery_payment_mode",
        "yookassa_receipt_product_subject",
        "yookassa_receipt_delivery_subject",
        mode="before",
    )
    @classmethod
    def empty_receipt_value_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_environment_contract(self) -> Settings:
        origins = self.cors_origin_list
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must not contain '*' when credentials are enabled")

        if self.database_enabled and not self.database_url:
            raise ValueError("DATABASE_URL is required when DATABASE_ENABLED is true")
        if self.catalog_reads_enabled and not self.database_enabled:
            raise ValueError("DATABASE_ENABLED must be true when CATALOG_READS_ENABLED is true")
        if self.catalog_reads_enabled and not self.minio_enabled:
            raise ValueError("MINIO_ENABLED must be true when CATALOG_READS_ENABLED is true")
        if self.catalog_reads_enabled and not re.fullmatch(
            r"[0-9a-f]{64}",
            self.catalog_migration_fingerprint or "",
        ):
            raise ValueError(
                "CATALOG_MIGRATION_FINGERPRINT must be a reviewed 64-character SHA-256 "
                "when CATALOG_READS_ENABLED is true"
            )
        if self.catalog_writes_enabled and not self.catalog_reads_enabled:
            raise ValueError(
                "CATALOG_READS_ENABLED must be true when CATALOG_WRITES_ENABLED is true"
            )
        if self.catalog_writes_enabled and not self.identity_api_enabled:
            raise ValueError(
                "IDENTITY_API_ENABLED must be true when CATALOG_WRITES_ENABLED is true"
            )
        if self.catalog_writes_enabled and not re.fullmatch(
            r"[0-9a-f]{64}",
            self.catalog_content_migration_fingerprint or "",
        ):
            raise ValueError(
                "CATALOG_CONTENT_MIGRATION_FINGERPRINT must be a reviewed 64-character "
                "SHA-256 when CATALOG_WRITES_ENABLED is true"
            )
        if self.carts_v2_enabled and not self.database_enabled:
            raise ValueError("DATABASE_ENABLED must be true when CARTS_V2_ENABLED is true")
        if self.carts_v2_enabled and not re.fullmatch(
            r"[0-9a-f]{64}",
            self.carts_migration_fingerprint or "",
        ):
            raise ValueError(
                "CARTS_MIGRATION_FINGERPRINT must be a reviewed 64-character SHA-256 "
                "when CARTS_V2_ENABLED is true"
            )
        if self.order_reads_enabled and not self.database_enabled:
            raise ValueError("DATABASE_ENABLED must be true when ORDER_READS_ENABLED is true")
        if self.order_reads_enabled and not self.identity_api_enabled:
            raise ValueError("IDENTITY_API_ENABLED must be true when ORDER_READS_ENABLED is true")
        if self.order_reads_enabled and not re.fullmatch(
            r"[0-9a-f]{64}",
            self.order_migration_fingerprint or "",
        ):
            raise ValueError(
                "ORDER_MIGRATION_FINGERPRINT must be a reviewed 64-character SHA-256 "
                "when ORDER_READS_ENABLED is true"
            )
        if self.checkout_v2_enabled:
            required_checkout_flags = {
                "CATALOG_READS_ENABLED": self.catalog_reads_enabled,
                "IDENTITY_API_ENABLED": self.identity_api_enabled,
                "ORDER_READS_ENABLED": self.order_reads_enabled,
                "PAYMENT_CREATION_ENABLED": self.payment_creation_enabled,
            }
            missing_checkout_flags = [
                name for name, enabled in required_checkout_flags.items() if not enabled
            ]
            if missing_checkout_flags:
                raise ValueError(
                    "Target checkout requires enabled dependencies: "
                    + ", ".join(missing_checkout_flags)
                )
        if self.partner_program_enabled:
            if not self.database_enabled:
                raise ValueError(
                    "DATABASE_ENABLED must be true when PARTNER_PROGRAM_ENABLED is true"
                )
            if not self.identity_api_enabled:
                raise ValueError(
                    "IDENTITY_API_ENABLED must be true when PARTNER_PROGRAM_ENABLED is true"
                )
            if not self.secret_value(self.partner_attribution_secret):
                raise ValueError(
                    "PARTNER_ATTRIBUTION_SECRET is required when PARTNER_PROGRAM_ENABLED is true"
                )
        if not 1 <= self.partner_attribution_days <= 365:
            raise ValueError("PARTNER_ATTRIBUTION_DAYS must be between 1 and 365")
        if not 0 <= self.partner_commission_hold_days <= 365:
            raise ValueError("PARTNER_COMMISSION_HOLD_DAYS must be between 0 and 365")
        for cookie_name in (
            self.partner_attribution_cookie_name,
            self.partner_visitor_cookie_name,
        ):
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cookie_name):
                raise ValueError("Partner cookie name contains unsupported characters")
        if self.partner_cookie_domain is not None:
            domain = self.partner_cookie_domain.strip().lower().lstrip(".")
            if not re.fullmatch(r"[a-z0-9.-]+", domain) or ".." in domain:
                raise ValueError("PARTNER_COOKIE_DOMAIN is invalid")
            self.partner_cookie_domain = f".{domain}"
        if self.crm_api_enabled and not self.database_enabled:
            raise ValueError("DATABASE_ENABLED must be true when CRM_API_ENABLED is true")
        if self.crm_api_enabled and not self.identity_api_enabled:
            raise ValueError("IDENTITY_API_ENABLED must be true when CRM_API_ENABLED is true")
        if self.crm_writes_enabled and not self.crm_api_enabled:
            raise ValueError("CRM_API_ENABLED must be true when CRM_WRITES_ENABLED is true")
        if self.crm_files_enabled and not self.crm_writes_enabled:
            raise ValueError("CRM_WRITES_ENABLED must be true when CRM_FILES_ENABLED is true")
        if self.crm_files_enabled and not self.minio_enabled:
            raise ValueError("MINIO_ENABLED must be true when CRM_FILES_ENABLED is true")

        if self.minio_enabled:
            required_minio = {
                "MINIO_ACCESS_KEY": self.minio_access_key,
                "MINIO_SECRET_KEY": self.minio_secret_key,
            }
            missing_minio = [
                name for name, value in required_minio.items() if not self.secret_value(value)
            ]
            if missing_minio:
                raise ValueError(f"Missing required MinIO settings: {', '.join(missing_minio)}")
            if not self.minio_endpoint.strip():
                raise ValueError("MINIO_ENDPOINT is required when MINIO_ENABLED is true")
            if "://" in self.minio_endpoint:
                raise ValueError("MINIO_ENDPOINT must be host[:port] without a URL scheme")
            endpoint = urlsplit(f"//{self.minio_endpoint.strip()}")
            if (
                not endpoint.hostname
                or endpoint.path
                or endpoint.query
                or endpoint.fragment
                or endpoint.username
                or endpoint.password
            ):
                raise ValueError("MINIO_ENDPOINT must contain only host[:port]")
            if not self.minio_public_base_url:
                raise ValueError("MINIO_PUBLIC_BASE_URL is required when MINIO_ENABLED is true")
            public_url = urlsplit(self.minio_public_base_url)
            if public_url.scheme not in {"http", "https"} or not public_url.netloc:
                raise ValueError("MINIO_PUBLIC_BASE_URL must be an absolute HTTP(S) URL")

        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,38}[a-z0-9]", self.minio_bucket_prefix):
            raise ValueError(
                "MINIO_BUCKET_PREFIX must contain 3-40 lowercase letters, digits or hyphens"
            )

        if not 60 <= self.minio_presigned_expire_seconds <= 604_800:
            raise ValueError("MINIO_PRESIGNED_EXPIRE_SECONDS must be between 60 and 604800")

        if self.media_max_upload_bytes <= 0:
            raise ValueError("MEDIA_MAX_UPLOAD_BYTES must be positive")
        if self.crm_file_max_upload_bytes <= 0 or (
            self.crm_files_enabled and self.crm_file_max_upload_bytes > self.media_max_upload_bytes
        ):
            raise ValueError(
                "CRM_FILE_MAX_UPLOAD_BYTES must be positive and not exceed MEDIA_MAX_UPLOAD_BYTES"
            )

        if not 60 <= self.inventory_reservation_ttl_seconds <= 86_400:
            raise ValueError("INVENTORY_RESERVATION_TTL_SECONDS must be between 60 and 86400")
        if not 1 <= self.order_guest_access_ttl_days <= 365:
            raise ValueError("ORDER_GUEST_ACCESS_TTL_DAYS must be between 1 and 365")

        if not 4 <= self.identity_otp_digits <= 8:
            raise ValueError("IDENTITY_OTP_DIGITS must be between 4 and 8")
        if not 1 <= self.identity_otp_max_attempts <= 10:
            raise ValueError("IDENTITY_OTP_MAX_ATTEMPTS must be between 1 and 10")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.identity_refresh_cookie_name):
            raise ValueError("IDENTITY_REFRESH_COOKIE_NAME contains unsupported characters")
        if (
            self.identity_legacy_token_grace_until is not None
            and self.identity_legacy_token_grace_until.tzinfo is None
        ):
            raise ValueError("IDENTITY_LEGACY_TOKEN_GRACE_UNTIL must include a timezone")
        if (
            self.identity_legacy_token_grace_until is not None
            and self.identity_legacy_token_grace_until
            > datetime.now(timezone.utc) + timedelta(days=31)
        ):
            raise ValueError("IDENTITY_LEGACY_TOKEN_GRACE_UNTIL must be within 31 days")
        identity_positive_fields = {
            "IDENTITY_OTP_EXPIRE_MINUTES": self.identity_otp_expire_minutes,
            "IDENTITY_OTP_RESEND_SECONDS": self.identity_otp_resend_seconds,
            "IDENTITY_OTP_HOURLY_LIMIT": self.identity_otp_hourly_limit,
            "IDENTITY_ACCESS_EXPIRE_MINUTES": self.identity_access_expire_minutes,
            "IDENTITY_REFRESH_EXPIRE_DAYS": self.identity_refresh_expire_days,
            "IDENTITY_MAX_ACTIVE_SESSIONS": self.identity_max_active_sessions,
        }
        invalid_identity_fields = [
            name for name, value in identity_positive_fields.items() if value <= 0
        ]
        if invalid_identity_fields:
            raise ValueError(
                f"Identity settings must be positive: {', '.join(invalid_identity_fields)}"
            )

        if self.identity_api_enabled:
            if not self.database_enabled:
                raise ValueError("DATABASE_ENABLED must be true when IDENTITY_API_ENABLED is true")
            if not re.fullmatch(r"[0-9a-f]{64}", self.identity_migration_fingerprint or ""):
                raise ValueError(
                    "IDENTITY_MIGRATION_FINGERPRINT must be a reviewed 64-character "
                    "SHA-256 when IDENTITY_API_ENABLED is true"
                )
            required_identity_secrets = {
                "JWT_SECRET": self.jwt_secret,
                "IDENTITY_OTP_PEPPER": self.identity_otp_pepper,
                "NOTIFICATION_ENCRYPTION_KEY": self.notification_encryption_key,
            }
            missing_identity = [
                name
                for name, value in required_identity_secrets.items()
                if not self.secret_value(value)
            ]
            if missing_identity:
                raise ValueError(
                    "Missing required identity API settings: " + ", ".join(missing_identity)
                )
            if self.identity_otp_digits != 4:
                raise ValueError(
                    "IDENTITY_OTP_DIGITS must remain 4 while the current frontend is active"
                )

        if self.notification_encryption_key_version <= 0:
            raise ValueError("NOTIFICATION_ENCRYPTION_KEY_VERSION must be positive")
        if not 1 <= self.notification_max_attempts <= 20:
            raise ValueError("NOTIFICATION_MAX_ATTEMPTS must be between 1 and 20")
        notification_positive_fields = {
            "NOTIFICATION_RETRY_BASE_SECONDS": self.notification_retry_base_seconds,
            "NOTIFICATION_RETRY_CAP_SECONDS": self.notification_retry_cap_seconds,
            "NOTIFICATION_PROCESSING_TIMEOUT_SECONDS": (
                self.notification_processing_timeout_seconds
            ),
            "NOTIFICATION_POLL_SECONDS": self.notification_poll_seconds,
        }
        invalid_notification_fields = [
            name for name, value in notification_positive_fields.items() if value <= 0
        ]
        if invalid_notification_fields:
            raise ValueError(
                f"Notification settings must be positive: {', '.join(invalid_notification_fields)}"
            )
        if self.notification_retry_cap_seconds < self.notification_retry_base_seconds:
            raise ValueError(
                "NOTIFICATION_RETRY_CAP_SECONDS must be greater than or equal to "
                "NOTIFICATION_RETRY_BASE_SECONDS"
            )

        cdek_url = urlsplit(self.cdek_api_url)
        if (
            cdek_url.scheme != "https"
            or not cdek_url.netloc
            or cdek_url.username
            or cdek_url.password
            or cdek_url.query
            or cdek_url.fragment
        ):
            raise ValueError("CDEK_API_URL must be an absolute HTTPS URL without credentials")
        if self.app_env in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION} and (
            cdek_url.hostname != "api.cdek.ru" or cdek_url.path.rstrip("/") != "/v2"
        ):
            raise ValueError("CDEK_API_URL must use https://api.cdek.ru/v2 outside local/test")
        if self.cdek_request_encryption_key_version <= 0:
            raise ValueError("CDEK_REQUEST_ENCRYPTION_KEY_VERSION must be positive")
        if not self.cdek_sender_name.strip():
            raise ValueError("CDEK_SENDER_NAME must not be blank")
        cdek_positive_fields = {
            "CDEK_SENDER_CITY_CODE": self.cdek_sender_city_code,
            "CDEK_WAREHOUSE_TO_WAREHOUSE_TARIFF": (self.cdek_warehouse_to_warehouse_tariff),
            "CDEK_WAREHOUSE_TO_DOOR_TARIFF": self.cdek_warehouse_to_door_tariff,
        }
        invalid_cdek_fields = [name for name, value in cdek_positive_fields.items() if value <= 0]
        if invalid_cdek_fields:
            raise ValueError("CDEK settings must be positive: " + ", ".join(invalid_cdek_fields))
        if not 1 <= self.cdek_max_packages <= 1_000:
            raise ValueError("CDEK_MAX_PACKAGES must be between 1 and 1000")
        if not 1 <= self.cdek_creation_max_attempts <= 20:
            raise ValueError("CDEK_CREATION_MAX_ATTEMPTS must be between 1 and 20")
        if not 1 <= self.cdek_timeout_seconds <= 60:
            raise ValueError("CDEK_TIMEOUT_SECONDS must be between 1 and 60")
        cdek_worker_positive_fields = {
            "CDEK_RETRY_BASE_SECONDS": self.cdek_retry_base_seconds,
            "CDEK_RETRY_CAP_SECONDS": self.cdek_retry_cap_seconds,
            "CDEK_PROCESSING_TIMEOUT_SECONDS": self.cdek_processing_timeout_seconds,
            "CDEK_POLL_SECONDS": self.cdek_poll_seconds,
        }
        invalid_cdek_worker_fields = [
            name for name, value in cdek_worker_positive_fields.items() if value <= 0
        ]
        if invalid_cdek_worker_fields:
            raise ValueError(
                "CDEK worker settings must be positive: " + ", ".join(invalid_cdek_worker_fields)
            )
        if self.cdek_retry_cap_seconds < self.cdek_retry_base_seconds:
            raise ValueError(
                "CDEK_RETRY_CAP_SECONDS must be greater than or equal to CDEK_RETRY_BASE_SECONDS"
            )
        if self.cdek_processing_timeout_seconds <= self.cdek_timeout_seconds:
            raise ValueError("CDEK_PROCESSING_TIMEOUT_SECONDS must exceed CDEK_TIMEOUT_SECONDS")
        if self.fulfillment_cdek_enabled:
            if not self.fulfillment_outbox_enabled:
                raise ValueError(
                    "FULFILLMENT_OUTBOX_ENABLED must be true when FULFILLMENT_CDEK_ENABLED is true"
                )
            if not self.secret_value(self.cdek_request_encryption_key):
                raise ValueError(
                    "CDEK_REQUEST_ENCRYPTION_KEY is required when FULFILLMENT_CDEK_ENABLED is true"
                )
        if self.cdek_quote_enabled:
            required_cdek_quote_flags = {
                "DATABASE_ENABLED": self.database_enabled,
                "CATALOG_READS_ENABLED": self.catalog_reads_enabled,
            }
            missing_cdek_quote_flags = [
                name for name, enabled in required_cdek_quote_flags.items() if not enabled
            ]
            if missing_cdek_quote_flags:
                raise ValueError(
                    "Target CDEK quote requires enabled dependencies: "
                    + ", ".join(missing_cdek_quote_flags)
                )
            required_cdek_quote = {
                "CDEK_CLIENT_ID": self.cdek_client_id,
                "CDEK_CLIENT_SECRET": self.cdek_client_secret,
            }
            missing_cdek_quote = [
                name for name, value in required_cdek_quote.items() if not self.secret_value(value)
            ]
            if missing_cdek_quote:
                raise ValueError(
                    "Missing required CDEK quote settings: " + ", ".join(missing_cdek_quote)
                )
        if self.cdek_creation_enabled:
            if not self.database_enabled:
                raise ValueError("DATABASE_ENABLED must be true when CDEK_CREATION_ENABLED is true")
            if not self.fulfillment_cdek_enabled:
                raise ValueError(
                    "FULFILLMENT_CDEK_ENABLED must be true when CDEK_CREATION_ENABLED is true"
                )
            required_cdek_creation = {
                "CDEK_CLIENT_ID": self.cdek_client_id,
                "CDEK_CLIENT_SECRET": self.cdek_client_secret,
                "CDEK_REQUEST_ENCRYPTION_KEY": self.cdek_request_encryption_key,
            }
            missing_cdek_creation = [
                name
                for name, value in required_cdek_creation.items()
                if not self.secret_value(value)
            ]
            if missing_cdek_creation:
                raise ValueError(
                    "Missing required CDEK creation settings: " + ", ".join(missing_cdek_creation)
                )

        yookassa_url = urlsplit(self.yookassa_api_url)
        if (
            yookassa_url.scheme != "https"
            or not yookassa_url.netloc
            or yookassa_url.username
            or yookassa_url.password
            or yookassa_url.query
            or yookassa_url.fragment
        ):
            raise ValueError("YOOKASSA_API_URL must be an absolute HTTPS URL without credentials")
        if self.app_env in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION} and (
            yookassa_url.hostname != "api.yookassa.ru" or yookassa_url.path.rstrip("/") != "/v3"
        ):
            raise ValueError(
                "YOOKASSA_API_URL must use https://api.yookassa.ru/v3 outside local/test"
            )
        if not 1 <= self.yookassa_timeout_seconds <= 60:
            raise ValueError("YOOKASSA_TIMEOUT_SECONDS must be between 1 and 60")
        if not 60 <= self.payment_creation_retry_window_seconds <= 86_400:
            raise ValueError("PAYMENT_CREATION_RETRY_WINDOW_SECONDS must be between 60 and 86400")
        if not 1 <= self.payment_creation_processing_timeout_seconds <= 3_600:
            raise ValueError(
                "PAYMENT_CREATION_PROCESSING_TIMEOUT_SECONDS must be between 1 and 3600"
            )
        if self.payment_creation_processing_timeout_seconds <= self.yookassa_timeout_seconds:
            raise ValueError(
                "PAYMENT_CREATION_PROCESSING_TIMEOUT_SECONDS must exceed YOOKASSA_TIMEOUT_SECONDS"
            )
        if not 1 <= self.payment_operation_processing_timeout_seconds <= 3_600:
            raise ValueError(
                "PAYMENT_OPERATION_PROCESSING_TIMEOUT_SECONDS must be between 1 and 3600"
            )
        if self.payment_operation_processing_timeout_seconds <= self.yookassa_timeout_seconds:
            raise ValueError(
                "PAYMENT_OPERATION_PROCESSING_TIMEOUT_SECONDS must exceed YOOKASSA_TIMEOUT_SECONDS"
            )
        if self.payment_management_enabled:
            required_payment_management = {
                "DATABASE_ENABLED": self.database_enabled,
                "IDENTITY_API_ENABLED": self.identity_api_enabled,
                "PAYMENT_CREATION_ENABLED": self.payment_creation_enabled,
            }
            missing_payment_management = [
                name for name, enabled in required_payment_management.items() if not enabled
            ]
            if missing_payment_management:
                raise ValueError(
                    "Payment management requires enabled dependencies: "
                    + ", ".join(missing_payment_management)
                )
            if not (self.payment_webhook_v2_enabled or self.payment_reconciliation_enabled):
                raise ValueError(
                    "Payment management requires PAYMENT_WEBHOOK_V2_ENABLED or "
                    "PAYMENT_RECONCILIATION_ENABLED"
                )
        if not 60 <= self.payout_retry_window_seconds <= 86_400:
            raise ValueError("PAYOUT_RETRY_WINDOW_SECONDS must be between 60 and 86400")
        if not 1 <= self.payout_processing_timeout_seconds <= 3_600:
            raise ValueError("PAYOUT_PROCESSING_TIMEOUT_SECONDS must be between 1 and 3600")
        if self.payout_processing_timeout_seconds <= self.yookassa_timeout_seconds:
            raise ValueError(
                "PAYOUT_PROCESSING_TIMEOUT_SECONDS must exceed YOOKASSA_TIMEOUT_SECONDS"
            )
        if self.yookassa_payouts_enabled:
            required_payout_flags = {
                "DATABASE_ENABLED": self.database_enabled,
                "IDENTITY_API_ENABLED": self.identity_api_enabled,
            }
            missing_payout_flags = [
                name for name, enabled in required_payout_flags.items() if not enabled
            ]
            if missing_payout_flags:
                raise ValueError(
                    "YooKassa payouts require enabled dependencies: "
                    + ", ".join(missing_payout_flags)
                )
            required_payout_secrets = {
                "YOOKASSA_PAYOUT_AGENT_ID": self.yookassa_payout_agent_id,
                "YOOKASSA_PAYOUT_API_KEY": self.yookassa_payout_api_key,
            }
            missing_payout_secrets = [
                name
                for name, value in required_payout_secrets.items()
                if not self.secret_value(value)
            ]
            if missing_payout_secrets:
                raise ValueError(
                    "Missing required YooKassa payout settings: "
                    + ", ".join(missing_payout_secrets)
                )
        if not 1 <= self.payment_max_attempts_per_order <= 10:
            raise ValueError("PAYMENT_MAX_ATTEMPTS_PER_ORDER must be between 1 and 10")
        if not 1 <= self.fulfillment_max_attempts <= 20:
            raise ValueError("FULFILLMENT_MAX_ATTEMPTS must be between 1 and 20")
        if self.fulfillment_outbox_enabled and not self.database_enabled:
            raise ValueError(
                "DATABASE_ENABLED must be true when FULFILLMENT_OUTBOX_ENABLED is true"
            )
        fulfillment_positive_fields = {
            "FULFILLMENT_RETRY_BASE_SECONDS": self.fulfillment_retry_base_seconds,
            "FULFILLMENT_RETRY_CAP_SECONDS": self.fulfillment_retry_cap_seconds,
            "FULFILLMENT_PROCESSING_TIMEOUT_SECONDS": (self.fulfillment_processing_timeout_seconds),
            "FULFILLMENT_POLL_SECONDS": self.fulfillment_poll_seconds,
        }
        invalid_fulfillment_fields = [
            name for name, value in fulfillment_positive_fields.items() if value <= 0
        ]
        if invalid_fulfillment_fields:
            raise ValueError(
                "Fulfillment settings must be positive: " + ", ".join(invalid_fulfillment_fields)
            )
        if self.fulfillment_retry_cap_seconds < self.fulfillment_retry_base_seconds:
            raise ValueError(
                "FULFILLMENT_RETRY_CAP_SECONDS must be greater than or equal to "
                "FULFILLMENT_RETRY_BASE_SECONDS"
            )
        if self.fulfillment_email_enabled:
            if not self.fulfillment_outbox_enabled:
                raise ValueError(
                    "FULFILLMENT_OUTBOX_ENABLED must be true when FULFILLMENT_EMAIL_ENABLED is true"
                )
            required_email = {
                "NOTIFICATION_ENCRYPTION_KEY": self.notification_encryption_key,
                "SMTP_PASSWORD": self.smtp_password,
            }
            missing_email = [
                name for name, value in required_email.items() if not self.secret_value(value)
            ]
            if missing_email:
                raise ValueError(
                    "Missing required email fulfillment settings: " + ", ".join(missing_email)
                )
        if self.fulfillment_crm_enabled and not self.fulfillment_outbox_enabled:
            raise ValueError(
                "FULFILLMENT_OUTBOX_ENABLED must be true when FULFILLMENT_CRM_ENABLED is true"
            )
        receipt_codes = {
            "YOOKASSA_RECEIPT_PRODUCT_VAT_CODE": self.yookassa_receipt_product_vat_code,
            "YOOKASSA_RECEIPT_DELIVERY_VAT_CODE": self.yookassa_receipt_delivery_vat_code,
        }
        invalid_receipt_codes = [
            name
            for name, value in receipt_codes.items()
            if value is not None and not 1 <= value <= 12
        ]
        if invalid_receipt_codes:
            raise ValueError(
                "YooKassa receipt VAT codes must be between 1 and 12: "
                + ", ".join(invalid_receipt_codes)
            )
        if self.yookassa_receipt_tax_system_code is not None and not (
            1 <= self.yookassa_receipt_tax_system_code <= 6
        ):
            raise ValueError("YOOKASSA_RECEIPT_TAX_SYSTEM_CODE must be between 1 and 6")
        receipt_modes = {
            "YOOKASSA_RECEIPT_PRODUCT_PAYMENT_MODE": (self.yookassa_receipt_product_payment_mode),
            "YOOKASSA_RECEIPT_DELIVERY_PAYMENT_MODE": (self.yookassa_receipt_delivery_payment_mode),
        }
        invalid_receipt_modes = [
            name
            for name, value in receipt_modes.items()
            if value is not None and value not in YOOKASSA_RECEIPT_PAYMENT_MODES
        ]
        if invalid_receipt_modes:
            raise ValueError(
                "Unsupported YooKassa receipt payment modes: " + ", ".join(invalid_receipt_modes)
            )
        if (
            self.yookassa_receipt_product_subject is not None
            and self.yookassa_receipt_product_subject not in YOOKASSA_RECEIPT_PRODUCT_SUBJECTS
        ):
            raise ValueError(
                "YOOKASSA_RECEIPT_PRODUCT_SUBJECT must be commodity or non_marked; "
                "marked goods require a separate marking-code implementation"
            )
        if (
            self.yookassa_receipt_delivery_subject is not None
            and self.yookassa_receipt_delivery_subject not in YOOKASSA_RECEIPT_DELIVERY_SUBJECTS
        ):
            raise ValueError("YOOKASSA_RECEIPT_DELIVERY_SUBJECT must be service")
        if self.payment_creation_enabled:
            if not self.database_enabled:
                raise ValueError(
                    "DATABASE_ENABLED must be true when PAYMENT_CREATION_ENABLED is true"
                )
            required_creation = {
                "YOOKASSA_SHOP_ID": self.secret_value(self.yookassa_shop_id),
                "YOOKASSA_API_KEY": self.secret_value(self.yookassa_api_key),
                **receipt_codes,
                **receipt_modes,
                "YOOKASSA_RECEIPT_PRODUCT_SUBJECT": (self.yookassa_receipt_product_subject),
                "YOOKASSA_RECEIPT_DELIVERY_SUBJECT": (self.yookassa_receipt_delivery_subject),
            }
            missing_creation = [
                name for name, value in required_creation.items() if value is None or value == ""
            ]
            if missing_creation:
                raise ValueError(
                    "Missing required payment creation settings: " + ", ".join(missing_creation)
                )
            public_url = urlsplit(self.public_base_url)
            allowed_public_schemes = (
                {"http", "https"}
                if self.app_env in {AppEnvironment.LOCAL, AppEnvironment.TEST}
                else {"https"}
            )
            if (
                public_url.scheme not in allowed_public_schemes
                or not public_url.netloc
                or public_url.username
                or public_url.password
                or public_url.query
                or public_url.fragment
            ):
                raise ValueError(
                    "PUBLIC_BASE_URL must be an absolute safe URL for payment creation"
                )
        if not 1 <= self.payment_event_max_attempts <= 20:
            raise ValueError("PAYMENT_EVENT_MAX_ATTEMPTS must be between 1 and 20")
        payment_event_positive_fields = {
            "PAYMENT_EVENT_RETRY_BASE_SECONDS": self.payment_event_retry_base_seconds,
            "PAYMENT_EVENT_RETRY_CAP_SECONDS": self.payment_event_retry_cap_seconds,
            "PAYMENT_EVENT_PROCESSING_TIMEOUT_SECONDS": (
                self.payment_event_processing_timeout_seconds
            ),
            "PAYMENT_EVENT_POLL_SECONDS": self.payment_event_poll_seconds,
        }
        invalid_payment_event_fields = [
            name for name, value in payment_event_positive_fields.items() if value <= 0
        ]
        if invalid_payment_event_fields:
            raise ValueError(
                "Payment event settings must be positive: "
                + ", ".join(invalid_payment_event_fields)
            )
        if self.payment_event_retry_cap_seconds < self.payment_event_retry_base_seconds:
            raise ValueError(
                "PAYMENT_EVENT_RETRY_CAP_SECONDS must be greater than or equal to "
                "PAYMENT_EVENT_RETRY_BASE_SECONDS"
            )
        if self.payment_event_processing_timeout_seconds <= self.yookassa_timeout_seconds:
            raise ValueError(
                "PAYMENT_EVENT_PROCESSING_TIMEOUT_SECONDS must exceed YOOKASSA_TIMEOUT_SECONDS"
            )
        if self.payment_webhook_v2_enabled and not self.database_enabled:
            raise ValueError(
                "DATABASE_ENABLED must be true when PAYMENT_WEBHOOK_V2_ENABLED is true"
            )
        try:
            trusted_proxy_networks = self.payment_webhook_trusted_proxy_networks
        except ValueError as error:
            raise ValueError(
                "PAYMENT_WEBHOOK_TRUSTED_PROXY_CIDRS must contain valid IP networks"
            ) from error
        if any(network.prefixlen == 0 for network in trusted_proxy_networks):
            raise ValueError(
                "PAYMENT_WEBHOOK_TRUSTED_PROXY_CIDRS must not trust an entire IP family"
            )
        if self.payment_reconciliation_enabled:
            if not self.database_enabled:
                raise ValueError(
                    "DATABASE_ENABLED must be true when PAYMENT_RECONCILIATION_ENABLED is true"
                )
            required_reconciliation_secrets = {
                "YOOKASSA_SHOP_ID": self.yookassa_shop_id,
                "YOOKASSA_API_KEY": self.yookassa_api_key,
            }
            missing_reconciliation = [
                name
                for name, value in required_reconciliation_secrets.items()
                if not self.secret_value(value)
            ]
            if missing_reconciliation:
                raise ValueError(
                    "Missing required reconciliation settings: " + ", ".join(missing_reconciliation)
                )
        if not 1 <= self.payment_reconciliation_max_attempts <= 1_000:
            raise ValueError("PAYMENT_RECONCILIATION_MAX_ATTEMPTS must be between 1 and 1000")
        reconciliation_positive_fields = {
            "PAYMENT_RECONCILIATION_INTERVAL_SECONDS": (
                self.payment_reconciliation_interval_seconds
            ),
            "PAYMENT_RECONCILIATION_RETRY_BASE_SECONDS": (
                self.payment_reconciliation_retry_base_seconds
            ),
            "PAYMENT_RECONCILIATION_RETRY_CAP_SECONDS": (
                self.payment_reconciliation_retry_cap_seconds
            ),
            "PAYMENT_RECONCILIATION_PROCESSING_TIMEOUT_SECONDS": (
                self.payment_reconciliation_processing_timeout_seconds
            ),
            "PAYMENT_RECONCILIATION_POLL_SECONDS": self.payment_reconciliation_poll_seconds,
        }
        invalid_reconciliation_fields = [
            name for name, value in reconciliation_positive_fields.items() if value <= 0
        ]
        if invalid_reconciliation_fields:
            raise ValueError(
                "Payment reconciliation settings must be positive: "
                + ", ".join(invalid_reconciliation_fields)
            )
        if (
            self.payment_reconciliation_retry_cap_seconds
            < self.payment_reconciliation_retry_base_seconds
        ):
            raise ValueError(
                "PAYMENT_RECONCILIATION_RETRY_CAP_SECONDS must be greater than or equal to "
                "PAYMENT_RECONCILIATION_RETRY_BASE_SECONDS"
            )
        if self.payment_reconciliation_processing_timeout_seconds <= self.yookassa_timeout_seconds:
            raise ValueError(
                "PAYMENT_RECONCILIATION_PROCESSING_TIMEOUT_SECONDS must exceed "
                "YOOKASSA_TIMEOUT_SECONDS"
            )

        if self.app_env is AppEnvironment.PRODUCTION:
            required_secrets = {
                "JWT_SECRET": self.jwt_secret,
                "CDEK_CLIENT_ID": self.cdek_client_id,
                "CDEK_CLIENT_SECRET": self.cdek_client_secret,
                "YOOKASSA_SHOP_ID": self.yookassa_shop_id,
                "YOOKASSA_API_KEY": self.yookassa_api_key,
                "SMTP_PASSWORD": self.smtp_password,
            }
            missing = [
                name for name, value in required_secrets.items() if not self.secret_value(value)
            ]
            if missing:
                raise ValueError(
                    f"Missing required {self.app_env.value} settings: {', '.join(missing)}"
                )

            if len(self.secret_value(self.jwt_secret)) < 32:
                raise ValueError("JWT_SECRET must contain at least 32 characters")

        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return list(
            dict.fromkeys(
                origin.strip().rstrip("/")
                for origin in self.cors_origins.split(",")
                if origin.strip()
            )
        )

    @property
    def payment_webhook_url(self) -> str:
        if self.yookassa_webhook_url:
            return self.yookassa_webhook_url
        return f"{self.public_base_url.rstrip('/')}/api/webhooks/yookassa"

    @property
    def payment_webhook_trusted_proxy_networks(
        self,
    ) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
        return tuple(
            ipaddress.ip_network(value.strip(), strict=True)
            for value in self.payment_webhook_trusted_proxy_cidrs.split(",")
            if value.strip()
        )

    @property
    def minio_media_bucket(self) -> str:
        return f"{self.minio_bucket_prefix}-{self.app_env.value}-media"

    @property
    def minio_crm_bucket(self) -> str:
        return f"{self.minio_bucket_prefix}-{self.app_env.value}-crm-private"

    def require_secret(self, field_name: str, label: str) -> str:
        value = self.secret_value(getattr(self, field_name))
        if not value:
            raise ConfigurationError(f"{label} is not configured")
        return value

    @staticmethod
    def secret_value(value: SecretStr | None) -> str:
        return value.get_secret_value().strip() if value is not None else ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
