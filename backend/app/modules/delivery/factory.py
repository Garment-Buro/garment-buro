from __future__ import annotations

import json

from app.core.config import Settings
from app.modules.delivery.crypto import CdekRequestCodec


def build_cdek_request_codec(settings: Settings) -> CdekRequestCodec:
    current_key = settings.require_secret(
        "cdek_request_encryption_key",
        "CDEK_REQUEST_ENCRYPTION_KEY",
    )
    encoded_previous = Settings.secret_value(settings.cdek_previous_request_encryption_keys)
    try:
        previous_payload = json.loads(encoded_previous or "{}")
        if not isinstance(previous_payload, dict):
            raise ValueError
        encoded_keys = {int(version): str(value) for version, value in previous_payload.items()}
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("CDEK_PREVIOUS_REQUEST_ENCRYPTION_KEYS must be a JSON object") from error
    encoded_keys[settings.cdek_request_encryption_key_version] = current_key
    return CdekRequestCodec.from_base64_keys(
        encoded_keys,
        current_version=settings.cdek_request_encryption_key_version,
    )
