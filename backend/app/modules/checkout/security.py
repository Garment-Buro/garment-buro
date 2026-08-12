from __future__ import annotations

import base64
import hashlib

from app.modules.orders.security import normalize_order_idempotency_key

PAYMENT_ATTEMPT_KEY_DOMAIN = b"garment-buro:checkout-payment-attempt:v1\x00"


def derive_checkout_payment_attempt_key(checkout_idempotency_key: str) -> str:
    normalized = normalize_order_idempotency_key(checkout_idempotency_key)
    digest = hashlib.sha256(PAYMENT_ATTEMPT_KEY_DOMAIN + normalized.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
