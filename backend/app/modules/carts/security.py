import hashlib
import re

CART_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


class InvalidCartIdError(ValueError):
    pass


def normalize_cart_id(cart_id: str) -> str:
    normalized = (cart_id or "").strip()
    if not CART_ID_PATTERN.fullmatch(normalized):
        raise InvalidCartIdError("Invalid cart id")
    return normalized


def digest_cart_id(cart_id: str) -> str:
    return hashlib.sha256(normalize_cart_id(cart_id).encode("utf-8")).hexdigest()
