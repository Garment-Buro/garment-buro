from __future__ import annotations

import re

PHONE_SEPARATORS = re.compile(r"[\s()\-]")
NORMALIZED_PHONE = re.compile(r"^\+?[0-9]{7,15}$")


def normalize_cdek_phone(value: str | None) -> str:
    normalized = PHONE_SEPARATORS.sub("", value or "")
    if not NORMALIZED_PHONE.fullmatch(normalized):
        raise ValueError("cdek_phone_invalid")
    return normalized
