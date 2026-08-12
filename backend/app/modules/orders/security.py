import hashlib
import re
import secrets

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
GUEST_ACCESS_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class InvalidOrderIdempotencyKeyError(ValueError):
    pass


class InvalidOrderGuestAccessTokenError(ValueError):
    pass


def normalize_order_idempotency_key(value: str) -> str:
    normalized = (value or "").strip()
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(normalized):
        raise InvalidOrderIdempotencyKeyError("Invalid order idempotency key")
    return normalized


def digest_order_idempotency_key(value: str) -> str:
    normalized = normalize_order_idempotency_key(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_order_guest_access_token() -> str:
    return secrets.token_urlsafe(32)


def normalize_order_guest_access_token(value: str) -> str:
    normalized = (value or "").strip()
    if not GUEST_ACCESS_TOKEN_PATTERN.fullmatch(normalized):
        raise InvalidOrderGuestAccessTokenError("Invalid order guest access token")
    return normalized


def digest_order_guest_access_token(value: str) -> str:
    normalized = normalize_order_guest_access_token(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
