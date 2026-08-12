from __future__ import annotations

import hashlib
import ipaddress
import re
from collections.abc import Sequence

PAYMENT_ATTEMPT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
YOOKASSA_WEBHOOK_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "185.71.76.0/27",
        "185.71.77.0/27",
        "77.75.153.0/25",
        "77.75.156.11/32",
        "77.75.156.35/32",
        "77.75.154.128/25",
        "2a02:5180::/32",
    )
)
MAX_FORWARDED_FOR_BYTES = 2_048
MAX_FORWARDED_FOR_HOPS = 16


class InvalidPaymentAttemptKeyError(ValueError):
    pass


class InvalidPaymentWebhookSourceError(ValueError):
    pass


def digest_payment_attempt_key(value: str) -> str:
    normalized = (value or "").strip()
    if not PAYMENT_ATTEMPT_KEY_PATTERN.fullmatch(normalized):
        raise InvalidPaymentAttemptKeyError("Invalid payment attempt key")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_trusted_yookassa_webhook_ip(value: str) -> bool:
    try:
        address = normalize_ip_address(value)
    except InvalidPaymentWebhookSourceError:
        return False
    return any(address in network for network in YOOKASSA_WEBHOOK_NETWORKS)


def resolve_payment_webhook_source_ip(
    *,
    peer_ip: str | None,
    forwarded_for: str | None,
    trusted_proxy_networks: Sequence[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> str:
    if peer_ip is None:
        raise InvalidPaymentWebhookSourceError("Webhook peer address is unavailable")
    peer = normalize_ip_address(peer_ip)
    if not _address_in_networks(peer, trusted_proxy_networks):
        return str(peer)
    if forwarded_for is None or not forwarded_for.strip():
        raise InvalidPaymentWebhookSourceError("Trusted proxy omitted the forwarding chain")
    if len(forwarded_for.encode("utf-8")) > MAX_FORWARDED_FOR_BYTES:
        raise InvalidPaymentWebhookSourceError("Webhook forwarding chain is too large")
    raw_hops = forwarded_for.split(",")
    if not 1 <= len(raw_hops) <= MAX_FORWARDED_FOR_HOPS:
        raise InvalidPaymentWebhookSourceError("Webhook forwarding chain has too many hops")
    forwarded = [normalize_ip_address(value) for value in raw_hops]
    chain = [*forwarded, peer]
    while chain and _address_in_networks(chain[-1], trusted_proxy_networks):
        chain.pop()
    if not chain:
        raise InvalidPaymentWebhookSourceError("Webhook source contains only trusted proxies")
    return str(chain[-1])


def normalize_ip_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        address = ipaddress.ip_address(value.strip())
    except (AttributeError, ValueError) as error:
        raise InvalidPaymentWebhookSourceError("Webhook source address is invalid") from error
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address


def _address_in_networks(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    networks: Sequence[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    return any(address.version == network.version and address in network for network in networks)
