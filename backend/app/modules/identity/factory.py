from __future__ import annotations

import secrets
from datetime import timedelta

from app.core.config import Settings
from app.core.exceptions import ConfigurationError
from app.modules.identity.auth_methods.email import EmailOtpAuthMethod
from app.modules.identity.auth_methods.password import PasswordAuthMethod
from app.modules.identity.auth_methods.phone import PhoneOtpAuthMethod
from app.modules.identity.auth_methods.registry import AuthMethodRegistry
from app.modules.identity.auth_methods.telegram import TelegramAuthMethod
from app.modules.identity.security import OtpSecurity, TokenSecurity
from app.modules.identity.service import IdentityPolicy, IdentityService
from app.modules.identity.telegram import TelegramLoginVerifier


def build_identity_service(settings: Settings) -> IdentityService:
    """Build the dormant identity service only when its API boundary needs it."""
    otp_pepper = settings.require_secret("identity_otp_pepper", "IDENTITY_OTP_PEPPER")
    jwt_secret = settings.require_secret("jwt_secret", "JWT_SECRET")
    if secrets.compare_digest(otp_pepper, jwt_secret):
        raise ConfigurationError("IDENTITY_OTP_PEPPER must not equal JWT_SECRET")
    return IdentityService(
        OtpSecurity(
            otp_pepper,
            digits=settings.identity_otp_digits,
        ),
        TokenSecurity(
            jwt_secret,
            algorithm=settings.jwt_algorithm,
            access_lifetime=timedelta(minutes=settings.identity_access_expire_minutes),
        ),
        policy=IdentityPolicy(
            otp_lifetime=timedelta(minutes=settings.identity_otp_expire_minutes),
            otp_resend_interval=timedelta(seconds=settings.identity_otp_resend_seconds),
            otp_window_limit=settings.identity_otp_hourly_limit,
            otp_max_attempts=settings.identity_otp_max_attempts,
            refresh_lifetime=timedelta(days=settings.identity_refresh_expire_days),
            max_active_sessions=settings.identity_max_active_sessions,
            password_max_attempts=settings.identity_password_max_attempts,
            password_lockout=timedelta(minutes=settings.identity_password_lockout_minutes),
        ),
    )


def build_auth_method_registry(settings: Settings) -> AuthMethodRegistry:
    telegram_verifier = None
    telegram_token = Settings.secret_value(settings.telegram_bot_token)
    if settings.identity_telegram_auth_enabled and telegram_token:
        telegram_verifier = TelegramLoginVerifier(
            telegram_token,
            max_age=timedelta(seconds=settings.telegram_auth_max_age_seconds),
        )
    return AuthMethodRegistry(
        [
            EmailOtpAuthMethod(),
            PasswordAuthMethod(enabled=settings.identity_password_auth_enabled),
            PhoneOtpAuthMethod(enabled=settings.identity_phone_auth_enabled),
            TelegramAuthMethod(
                telegram_verifier,
                disabled_reason=(
                    "disabled_by_configuration"
                    if not settings.identity_telegram_auth_enabled
                    else "bot_token_not_configured"
                ),
            ),
        ]
    )
