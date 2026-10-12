from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

import aiohttp
from anyio import to_thread

import email_service
from app.core.config import Settings
from app.modules.notifications.models import NotificationChannel
from app.modules.notifications.rendering import (
    RenderedEmail,
    RenderedNotification,
    RenderedTelegram,
)


class NotificationDeliveryError(RuntimeError):
    pass


class NotificationChannelUnavailableError(NotificationDeliveryError):
    pass


class NotificationTransport(Protocol):
    channel: str

    async def send(self, message: RenderedNotification) -> str | None: ...


class EmailTransport(Protocol):
    async def send(self, message: RenderedEmail) -> str | None: ...


class NotificationTransportRegistry:
    def __init__(self, transports: Iterable[NotificationTransport]) -> None:
        self._transports = {transport.channel: transport for transport in transports}

    def get(self, channel: str) -> NotificationTransport:
        transport = self._transports.get(channel)
        if transport is None:
            raise NotificationChannelUnavailableError(
                f"Notification channel is unavailable: {channel}"
            )
        return transport


class SmtpEmailTransport:
    channel = NotificationChannel.EMAIL.value

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, message: RenderedNotification) -> str | None:
        if not isinstance(message, RenderedEmail):
            raise NotificationDeliveryError("SMTP transport received a non-email message")
        delivered = await to_thread.run_sync(
            lambda: email_service.send_email(
                message.recipient,
                message.subject,
                message.html,
                settings=self.settings,
            )
        )
        if not delivered:
            raise NotificationDeliveryError("SMTP delivery failed")
        return None


class TelegramBotTransport:
    channel = NotificationChannel.TELEGRAM.value

    def __init__(self, *, bot_token: str, api_url: str, timeout_seconds: int = 10) -> None:
        self._bot_token = bot_token
        self._api_url = api_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def send(self, message: RenderedNotification) -> str | None:
        if not isinstance(message, RenderedTelegram):
            raise NotificationDeliveryError("Telegram transport received an invalid message")
        url = f"{self._api_url}/bot{self._bot_token}/sendMessage"
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(
                    url,
                    json={"chat_id": message.recipient, "text": message.text},
                ) as response:
                    status = response.status
                    payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            raise NotificationDeliveryError("Telegram delivery failed") from error
        if status >= 400 or not isinstance(payload, dict) or not payload.get("ok"):
            raise NotificationDeliveryError("Telegram delivery failed")
        result = payload.get("result")
        if isinstance(result, dict) and isinstance(result.get("message_id"), int):
            return str(result["message_id"])
        return None


class DisabledPhoneTransport:
    channel = NotificationChannel.PHONE.value

    async def send(self, _message: RenderedNotification) -> str | None:
        raise NotificationChannelUnavailableError("Phone provider is not configured")
