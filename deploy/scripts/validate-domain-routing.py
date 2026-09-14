#!/usr/bin/env python3
"""Guard the public domain to release-environment mapping."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def server_block(config: Path, hostname: str) -> str:
    text = config.read_text(encoding="utf-8")
    blocks = re.split(r"(?m)(?=^server\s*\{)", text)
    for block in blocks:
        if re.search(rf"(?m)^\s*server_name\s+{re.escape(hostname)}\s*;", block):
            return block
    raise AssertionError(f"{config}: missing server block for {hostname}")


def require(config: str, *fragments: str) -> None:
    for fragment in fragments:
        if fragment not in config:
            raise AssertionError(f"missing expected routing fragment: {fragment}")


def reject(config: str, *fragments: str) -> None:
    for fragment in fragments:
        if fragment in config:
            raise AssertionError(f"development route leaked into production host: {fragment}")


partner_legacy = server_block(ROOT / "nginx.conf", "partner.garment-buro.ru")
require(
    partner_legacy,
    "proxy_pass http://host.docker.internal:3200;",
    "proxy_pass http://host.docker.internal:8200;",
)
reject(partner_legacy, "host.docker.internal:3100")

partner_host = server_block(
    ROOT / "deploy/nginx/garment-buro.conf", "partner.garment-buro.ru"
)
require(
    partner_host,
    "proxy_pass http://127.0.0.1:3000;",
    "proxy_pass http://127.0.0.1:8000;",
)
reject(partner_host, "127.0.0.1:3100")

partner_snapshot = server_block(
    ROOT / "deploy/nginx/legacy-docker-production.conf.example",
    "partner.garment-buro.ru",
)
require(
    partner_snapshot,
    "proxy_pass http://172.17.0.1:3200;",
    "proxy_pass http://172.17.0.1:8200;",
)
reject(partner_snapshot, "172.17.0.1:3100")
