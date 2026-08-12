from __future__ import annotations

from typing import Protocol

from anyio import to_thread

import email_service
from app.core.config import Settings
from app.modules.notifications.rendering import RenderedEmail


class NotificationDeliveryError(RuntimeError):
    pass


class EmailTransport(Protocol):
    async def send(self, message: RenderedEmail) -> str | None: ...


class SmtpEmailTransport:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, message: RenderedEmail) -> str | None:
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
