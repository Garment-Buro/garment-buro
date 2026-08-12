from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.modules.identity.exceptions import InvalidEmailError, InvalidSessionError
from app.modules.identity.factory import build_identity_service
from app.modules.identity.models import OtpPurpose
from app.modules.identity.security import OtpSecurity, TokenSecurity, normalize_email


def test_otp_is_peppered_and_bound_to_context() -> None:
    security = OtpSecurity("p" * 32)
    salt = security.generate_salt()
    digest = security.digest(
        code="1234",
        salt=salt,
        purpose=OtpPurpose.LOGIN,
        target_email_normalized="user@example.test",
    )

    assert len(salt) == 32
    assert len(digest) == 64
    assert "1234" not in digest
    assert security.verify(
        code="1234",
        salt=salt,
        purpose=OtpPurpose.LOGIN,
        target_email_normalized="user@example.test",
        expected_digest=digest,
    )
    assert not security.verify(
        code="1234",
        salt=salt,
        purpose=OtpPurpose.EMAIL_CHANGE,
        target_email_normalized="user@example.test",
        expected_digest=digest,
    )
    assert not security.verify(
        code="4321",
        salt=salt,
        purpose=OtpPurpose.LOGIN,
        target_email_normalized="user@example.test",
        expected_digest=digest,
    )


def test_access_and_refresh_tokens_have_separate_contracts() -> None:
    security = TokenSecurity("j" * 32)
    now = datetime.now(timezone.utc)
    access_token, expires_at = security.create_access_token(
        user_id=42,
        session_id="77889a93-2ee7-42e1-a979-cce3e9995fc1",
        now=now,
    )
    claims = security.decode_access_token(access_token)

    assert claims.user_id == 42
    assert claims.session_id == "77889a93-2ee7-42e1-a979-cce3e9995fc1"
    assert claims.expires_at == expires_at.replace(microsecond=0)

    refresh_token = security.create_refresh_token()
    assert len(refresh_token) >= 64
    assert security.digest_refresh_token(refresh_token) != refresh_token
    with pytest.raises(InvalidSessionError):
        security.decode_access_token(refresh_token)


def test_email_normalization_preserves_display_value() -> None:
    assert normalize_email("  Customer@Example.TEST ") == (
        "Customer@Example.TEST",
        "customer@example.test",
    )
    with pytest.raises(InvalidEmailError):
        normalize_email("not-an-email")


@pytest.mark.parametrize("value", ["short", "x" * 31])
def test_identity_secrets_reject_short_values(value: str) -> None:
    with pytest.raises(ValueError, match="at least 32"):
        OtpSecurity(value)
    with pytest.raises(ValueError, match="at least 32"):
        TokenSecurity(value)


def test_identity_service_factory_requires_separate_pepper_and_short_access_token() -> None:
    missing_pepper = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        jwt_secret="j" * 32,
    )
    with pytest.raises(ConfigurationError, match="IDENTITY_OTP_PEPPER"):
        build_identity_service(missing_pepper)
    same_secret = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        jwt_secret="s" * 32,
        identity_otp_pepper="s" * 32,
    )
    with pytest.raises(ConfigurationError, match="must not equal"):
        build_identity_service(same_secret)

    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        identity_access_expire_minutes=12,
        identity_refresh_expire_days=21,
    )
    service = build_identity_service(settings)

    assert service.otp_security.digits == 4
    assert service.token_security.access_lifetime.total_seconds() == 12 * 60
    assert service.policy.refresh_lifetime.days == 21
