from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

from app.modules.identity.exceptions import InvalidEmailError, InvalidSessionError
from app.modules.identity.models import OtpPurpose

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SUPPORTED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: int
    session_id: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class LegacyAccessTokenClaims:
    user_id: int
    expires_at: datetime


class OtpSecurity:
    """Generate OTPs and persist only peppered HMAC digests."""

    def __init__(self, pepper: str, *, digits: int = 4) -> None:
        if len(pepper) < 32:
            raise ValueError("OTP pepper must contain at least 32 characters")
        if not 4 <= digits <= 8:
            raise ValueError("OTP digits must be between 4 and 8")
        self._pepper = pepper.encode("utf-8")
        self.digits = digits

    def generate_code(self) -> str:
        return "".join(str(secrets.randbelow(10)) for _ in range(self.digits))

    @staticmethod
    def generate_salt() -> str:
        return secrets.token_hex(16)

    def digest(
        self,
        *,
        code: str,
        salt: str,
        purpose: OtpPurpose,
        target_email_normalized: str,
    ) -> str:
        payload = "\0".join((salt, purpose.value, target_email_normalized, code))
        return hmac.new(self._pepper, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(
        self,
        *,
        code: str,
        salt: str,
        purpose: OtpPurpose,
        target_email_normalized: str,
        expected_digest: str,
    ) -> bool:
        actual = self.digest(
            code=code,
            salt=salt,
            purpose=purpose,
            target_email_normalized=target_email_normalized,
        )
        return hmac.compare_digest(actual, expected_digest)

    def digest_client_value(self, value: str | None) -> str | None:
        normalized = (value or "").strip()
        if not normalized:
            return None
        return hmac.new(
            self._pepper,
            normalized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


class TokenSecurity:
    """Issue short JWT access tokens and opaque hashed refresh tokens."""

    def __init__(
        self,
        secret: str,
        *,
        algorithm: str = "HS256",
        access_lifetime: timedelta = timedelta(minutes=15),
        clock_skew: timedelta = timedelta(seconds=60),
    ) -> None:
        if len(secret) < 32:
            raise ValueError("JWT secret must contain at least 32 characters")
        if algorithm not in SUPPORTED_JWT_ALGORITHMS:
            raise ValueError("JWT algorithm must be an HMAC SHA-2 algorithm")
        if access_lifetime <= timedelta(0):
            raise ValueError("Access token lifetime must be positive")
        if clock_skew < timedelta(0):
            raise ValueError("JWT clock skew must not be negative")
        self._secret = secret
        self.algorithm = algorithm
        self.access_lifetime = access_lifetime
        self.clock_skew = clock_skew

    def create_access_token(
        self,
        *,
        user_id: int,
        session_id: str,
        now: datetime,
    ) -> tuple[str, datetime]:
        now = ensure_utc(now)
        expires_at = now + self.access_lifetime
        token = jwt.encode(
            {
                "sub": str(user_id),
                "sid": session_id,
                "type": "access",
                "jti": str(uuid4()),
                "iat": now,
                "exp": expires_at,
            },
            self._secret,
            algorithm=self.algorithm,
        )
        return token, expires_at

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self.algorithm],
                leeway=self.clock_skew.total_seconds(),
                options={"require": ["sub", "sid", "type", "iat", "exp"]},
            )
            if payload.get("type") != "access":
                raise InvalidSessionError("Invalid access token type")
            user_id = int(payload["sub"])
            session_id = str(payload["sid"])
            expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
            raise InvalidSessionError("Invalid access token") from error
        if not session_id:
            raise InvalidSessionError("Invalid access token session")
        return AccessTokenClaims(
            user_id=user_id,
            session_id=session_id,
            expires_at=expires_at,
        )

    def decode_legacy_access_token(self, token: str) -> LegacyAccessTokenClaims:
        """Decode only the pre-cutover bearer shape during a bounded grace period."""
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self.algorithm],
                leeway=self.clock_skew.total_seconds(),
                options={"require": ["sub", "exp"]},
            )
            if payload.get("type") is not None or payload.get("sid") is not None:
                raise InvalidSessionError("Not a legacy access token")
            user_id = int(payload["sub"])
            expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
            raise InvalidSessionError("Invalid legacy access token") from error
        if user_id <= 0:
            raise InvalidSessionError("Invalid legacy access token subject")
        return LegacyAccessTokenClaims(user_id=user_id, expires_at=expires_at)

    @staticmethod
    def create_refresh_token() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def digest_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(value: str) -> tuple[str, str]:
    display = value.strip()
    normalized = display.casefold()
    if len(display) > 320 or not EMAIL_PATTERN.fullmatch(display):
        raise InvalidEmailError("Invalid email")
    return display, normalized


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
