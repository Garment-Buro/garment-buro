from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.modules.identity.security import ensure_utc


class InvalidPartnerAttributionTokenError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PartnerAttributionClaims:
    partner_id: int
    landing_id: int
    expires_at: datetime


class PartnerAttributionSecurity:
    def __init__(self, secret: str, *, lifetime: timedelta) -> None:
        if len(secret) < 32:
            raise ValueError("Partner attribution secret must contain at least 32 characters")
        if lifetime <= timedelta(0):
            raise ValueError("Partner attribution lifetime must be positive")
        self._secret = secret
        self._digest_key = secret.encode("utf-8")
        self.lifetime = lifetime

    def create_token(
        self,
        *,
        partner_id: int,
        landing_id: int,
        now: datetime,
    ) -> tuple[str, datetime]:
        issued_at = ensure_utc(now)
        expires_at = issued_at + self.lifetime
        token = jwt.encode(
            {
                "sub": str(partner_id),
                "landing_id": landing_id,
                "type": "partner_attribution",
                "iat": issued_at,
                "exp": expires_at,
            },
            self._secret,
            algorithm="HS256",
        )
        return token, expires_at

    def decode_token(self, token: str) -> PartnerAttributionClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                options={"require": ["sub", "landing_id", "type", "iat", "exp"]},
            )
            if payload.get("type") != "partner_attribution":
                raise InvalidPartnerAttributionTokenError("Invalid attribution token type")
            partner_id = int(payload["sub"])
            landing_id = int(payload["landing_id"])
            expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
            raise InvalidPartnerAttributionTokenError(
                "Invalid partner attribution token"
            ) from error
        if partner_id <= 0 or landing_id <= 0:
            raise InvalidPartnerAttributionTokenError("Invalid attribution subject")
        return PartnerAttributionClaims(
            partner_id=partner_id,
            landing_id=landing_id,
            expires_at=expires_at,
        )

    def digest_visitor(self, value: str) -> str:
        normalized = value.strip() or "anonymous"
        return hmac.new(
            self._digest_key,
            normalized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
