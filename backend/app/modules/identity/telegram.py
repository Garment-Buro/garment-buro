from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from app.modules.identity.exceptions import InvalidExternalAuthPayloadError
from app.modules.identity.service import ExternalAuthPrincipal


class TelegramLoginVerifier:
    """Validate payloads produced by the Telegram Login Widget."""

    provider = "telegram"

    def __init__(self, bot_token: str, *, max_age: timedelta) -> None:
        if not bot_token:
            raise ValueError("Telegram bot token is required")
        if max_age <= timedelta(0):
            raise ValueError("Telegram login max age must be positive")
        self._secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
        self.max_age = max_age

    def verify(
        self,
        payload: Mapping[str, str | int | None],
        *,
        now: datetime,
    ) -> ExternalAuthPrincipal:
        received_hash = payload.get("hash")
        if not isinstance(received_hash, str) or len(received_hash) != 64:
            raise InvalidExternalAuthPayloadError("Invalid Telegram signature")
        values = {
            key: str(value) for key, value in payload.items() if key != "hash" and value is not None
        }
        data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
        expected_hash = hmac.new(
            self._secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            raise InvalidExternalAuthPayloadError("Invalid Telegram signature")

        try:
            subject = str(values["id"])
            authenticated_at = datetime.fromtimestamp(int(values["auth_date"]), tz=timezone.utc)
        except (KeyError, OSError, OverflowError, TypeError, ValueError) as error:
            raise InvalidExternalAuthPayloadError("Invalid Telegram payload") from error
        current = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)
        if authenticated_at > current + timedelta(seconds=30):
            raise InvalidExternalAuthPayloadError("Telegram payload is from the future")
        if current - authenticated_at > self.max_age:
            raise InvalidExternalAuthPayloadError("Telegram payload has expired")
        if not subject.isdigit() or len(subject) > 64:
            raise InvalidExternalAuthPayloadError("Invalid Telegram user id")
        return ExternalAuthPrincipal(
            provider=self.provider,
            subject=subject,
            first_name=self._bounded(values.get("first_name"), 255),
            last_name=self._bounded(values.get("last_name"), 255),
            username=self._bounded(values.get("username"), 255),
        )

    @staticmethod
    def _bounded(value: str | None, maximum: int) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized[:maximum] or None
