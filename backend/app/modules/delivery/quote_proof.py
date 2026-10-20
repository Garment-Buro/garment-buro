"""Purpose-scoped shipping quote proofs; tokens contain no customer address."""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

import jwt

from app.core.config import Settings
from app.modules.identity.security import ensure_utc

if TYPE_CHECKING:
    from app.modules.delivery.quote_service import PreparedCdekQuote

QUOTE_VALIDITY_SECONDS = 15 * 60
QUOTE_AUDIENCE = "garment-buro-delivery-quote-v1"
MONEY_PATTERN = re.compile(r"^\d{1,10}\.\d{2}$")


class InvalidDeliveryQuoteError(ValueError):
    pass


class DeliveryQuoteProof:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _key(self) -> str:
        secret = self.settings.require_secret("jwt_secret", "JWT_SECRET")
        return hmac.new(secret.encode(), QUOTE_AUDIENCE.encode(), hashlib.sha256).hexdigest()

    def issue(
        self, prepared: PreparedCdekQuote, amount: Decimal, *, now: datetime | None = None
    ) -> str:
        if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
            raise InvalidDeliveryQuoteError("Invalid quoted delivery amount")
        rounded = amount.quantize(Decimal("0.01"))
        value = str(rounded)
        if rounded != amount or not MONEY_PATTERN.fullmatch(value):
            raise InvalidDeliveryQuoteError("Invalid quoted delivery amount")
        issued_at = int(ensure_utc(now or datetime.now(timezone.utc)).timestamp())
        return jwt.encode(
            {
                "aud": QUOTE_AUDIENCE,
                "iat": issued_at,
                "exp": issued_at + QUOTE_VALIDITY_SECONDS,
                "request": prepared.request_sha256,
                "amount": value,
            },
            self._key(),
            algorithm="HS256",
        )

    def verify(
        self, token: str, prepared: PreparedCdekQuote, *, now: datetime | None = None
    ) -> Decimal:
        if not token or len(token) > 4096:
            raise InvalidDeliveryQuoteError("Missing delivery quote")
        try:
            claims = jwt.decode(
                token,
                self._key(),
                algorithms=["HS256"],
                audience=QUOTE_AUDIENCE,
                options={
                    "verify_exp": False,
                    "verify_iat": False,
                    "require": ["aud", "iat", "exp", "request", "amount"],
                },
            )
            issued_at, expires_at = claims.get("iat"), claims.get("exp")
            current_time = int(ensure_utc(now or datetime.now(timezone.utc)).timestamp())
            if (
                type(issued_at) is not int
                or type(expires_at) is not int
                or expires_at - issued_at != QUOTE_VALIDITY_SECONDS
                or issued_at > current_time + 30
                or current_time >= expires_at
                or claims.get("aud") != QUOTE_AUDIENCE
            ):
                raise ValueError("Invalid delivery quote lifetime")
            request_hash = claims.get("request")
            value = claims.get("amount")
            if (
                not isinstance(request_hash, str)
                or not hmac.compare_digest(request_hash, prepared.request_sha256)
                or not isinstance(value, str)
                or not MONEY_PATTERN.fullmatch(value)
            ):
                raise ValueError("Delivery quote does not match the request")
            return Decimal(value)
        except (jwt.PyJWTError, ValueError, InvalidOperation) as error:
            raise InvalidDeliveryQuoteError("Invalid or expired delivery quote") from error
