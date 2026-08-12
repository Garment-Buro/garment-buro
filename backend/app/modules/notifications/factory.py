from __future__ import annotations

import json
from datetime import timedelta

from app.core.config import Settings
from app.modules.notifications.crypto import NotificationPayloadCodec
from app.modules.notifications.service import (
    NotificationDispatcher,
    NotificationOutboxService,
    NotificationPolicy,
)
from app.modules.notifications.transport import SmtpEmailTransport


def build_notification_codec(settings: Settings) -> NotificationPayloadCodec:
    current_key = settings.require_secret(
        "notification_encryption_key",
        "NOTIFICATION_ENCRYPTION_KEY",
    )
    encoded_previous = Settings.secret_value(settings.notification_previous_encryption_keys)
    try:
        previous_payload = json.loads(encoded_previous or "{}")
        if not isinstance(previous_payload, dict):
            raise ValueError
        encoded_keys = {int(version): str(value) for version, value in previous_payload.items()}
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("NOTIFICATION_PREVIOUS_ENCRYPTION_KEYS must be a JSON object") from error
    encoded_keys[settings.notification_encryption_key_version] = current_key
    return NotificationPayloadCodec.from_base64_keys(
        encoded_keys,
        current_version=settings.notification_encryption_key_version,
    )


def build_notification_policy(settings: Settings) -> NotificationPolicy:
    return NotificationPolicy(
        max_attempts=settings.notification_max_attempts,
        retry_base=timedelta(seconds=settings.notification_retry_base_seconds),
        retry_cap=timedelta(seconds=settings.notification_retry_cap_seconds),
        processing_timeout=timedelta(seconds=settings.notification_processing_timeout_seconds),
    )


def build_notification_outbox_service(settings: Settings) -> NotificationOutboxService:
    return NotificationOutboxService(
        build_notification_codec(settings),
        policy=build_notification_policy(settings),
    )


def build_notification_dispatcher(settings: Settings) -> NotificationDispatcher:
    return NotificationDispatcher(
        build_notification_codec(settings),
        SmtpEmailTransport(settings),
        policy=build_notification_policy(settings),
    )
