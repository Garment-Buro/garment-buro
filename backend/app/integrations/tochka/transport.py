from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass
from pathlib import Path

import aiohttp

from app.core.config import Settings
from app.modules.bank_payouts.contracts import BankProviderError

MAX_RESPONSE_BYTES = 256 * 1024
ROOT_CA = Path(__file__).with_name("russian_trusted_root_ca.pem")


def bank_ssl_context(ca_file: str | None = None) -> ssl.SSLContext:
    # This trust extension belongs only to this bank client, never the process/system.
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=ca_file or str(ROOT_CA))
    return context


@dataclass(frozen=True)
class BankHttpResponse:
    status: int
    body: bytes


class TochkaTransport:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = "https://enter.tochka.com/" + (
            "sandbox/v2" if settings.tochka_environment == "sandbox" else "uapi"
        )
        self.session: aiohttp.ClientSession | None = None

    async def startup(self) -> None:
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.settings.tochka_timeout_seconds),
                connector=aiohttp.TCPConnector(ssl=bank_ssl_context(self.settings.tochka_ca_file)),
                trust_env=False,
            )

    async def shutdown(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def request(self, method: str, path: str, body: bytes | None = None) -> BankHttpResponse:
        if self.session is None:
            raise BankProviderError("transport_not_started", outcome_unknown=False)
        token = (
            "sandbox.jwt.token"
            if self.settings.tochka_environment == "sandbox"
            else self.settings.secret_value(self.settings.tochka_api_token)
        )
        if not token:
            raise BankProviderError("token_not_configured", outcome_unknown=False)
        try:
            async with self.session.request(
                method,
                f"{self.base_url}{path}",
                data=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                allow_redirects=False,
            ) as response:
                chunks = bytearray()
                async for chunk in response.content.iter_chunked(16_384):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise BankProviderError("response_too_large")
                return BankHttpResponse(response.status, bytes(chunks))
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as error:
            # Never retry a POST: the bank may already have accepted it.
            raise BankProviderError("network_error") from error
