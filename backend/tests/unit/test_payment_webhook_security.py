from __future__ import annotations

import ipaddress

import pytest

from app.modules.payments.security import (
    InvalidPaymentWebhookSourceError,
    resolve_payment_webhook_source_ip,
)


def test_direct_peer_is_authoritative_without_a_trusted_proxy() -> None:
    assert (
        resolve_payment_webhook_source_ip(
            peer_ip="185.71.76.1",
            forwarded_for="203.0.113.10",
            trusted_proxy_networks=(),
        )
        == "185.71.76.1"
    )


def test_trusted_proxy_chain_is_walked_from_the_socket_peer() -> None:
    trusted = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("192.0.2.0/24"),
    )
    assert (
        resolve_payment_webhook_source_ip(
            peer_ip="10.0.0.5",
            forwarded_for="185.71.76.1, 192.0.2.8",
            trusted_proxy_networks=trusted,
        )
        == "185.71.76.1"
    )


def test_spoofed_leftmost_forwarded_address_is_not_selected() -> None:
    trusted = (ipaddress.ip_network("10.0.0.0/8"),)
    assert (
        resolve_payment_webhook_source_ip(
            peer_ip="10.0.0.5",
            forwarded_for="185.71.76.1, 198.51.100.7",
            trusted_proxy_networks=trusted,
        )
        == "198.51.100.7"
    )


@pytest.mark.parametrize(
    ("peer_ip", "forwarded_for"),
    [
        (None, None),
        ("not-an-ip", None),
        ("10.0.0.5", None),
        ("10.0.0.5", "bad-address"),
        ("10.0.0.5", ",".join(["192.0.2.1"] * 17)),
        ("10.0.0.5", "x" * 2_049),
    ],
)
def test_invalid_or_ambiguous_proxy_evidence_is_rejected(
    peer_ip: str | None,
    forwarded_for: str | None,
) -> None:
    with pytest.raises(InvalidPaymentWebhookSourceError):
        resolve_payment_webhook_source_ip(
            peer_ip=peer_ip,
            forwarded_for=forwarded_for,
            trusted_proxy_networks=(ipaddress.ip_network("10.0.0.0/8"),),
        )
