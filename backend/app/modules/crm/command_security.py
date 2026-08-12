from __future__ import annotations

import re

CRM_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~:-]{16,128}$")


class InvalidCrmIdempotencyKeyError(ValueError):
    pass


def normalize_crm_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not CRM_IDEMPOTENCY_KEY_PATTERN.fullmatch(normalized):
        raise InvalidCrmIdempotencyKeyError(
            "CRM Idempotency-Key must contain 16-128 allowlisted characters"
        )
    return normalized
