from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Protocol

import aiohttp
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.payouts.schemas import YooKassaPayoutResponse

MAX_YOOKASSA_PAYOUT_RESPONSE_BYTES = 256 * 1024
PAYOUT_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{36,50}$")


class YooKassaPayoutProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        rejected: bool = False,
        outcome_unknown: bool = False,
    ) -> None:
        super().__init__(f"YooKassa payout provider error: {code}")
        self.code = code
        self.retryable = retryable
        self.rejected = rejected
        self.outcome_unknown = outcome_unknown


@dataclass(frozen=True, slots=True)
class YooKassaPayoutHttpResponse:
    status: int
    body: bytes


class YooKassaPayoutHttpTransport(Protocol):
    async def create_payout(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaPayoutHttpResponse: ...

    async def get_payout(self, provider_payout_id: str) -> YooKassaPayoutHttpResponse: ...


class YooKassaPayoutProvider(Protocol):
    async def create_payout(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaPayoutResponse: ...

    async def get_payout(self, provider_payout_id: str) -> YooKassaPayoutResponse: ...


class AiohttpYooKassaPayoutTransport:
    """YooKassa payout transport with gateway credentials isolated from shop credentials."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.base_url = settings.yookassa_api_url.rstrip("/")
        self._agent_id = Settings.secret_value(settings.yookassa_payout_agent_id)
        self._api_key = Settings.secret_value(settings.yookassa_payout_api_key)
        self.timeout_seconds = settings.yookassa_timeout_seconds
        self._session = session
        self._owns_session = session is None

    async def startup(self) -> None:
        if self._session is not None:
            return
        if not self._agent_id or not self._api_key:
            raise YooKassaPayoutProviderError("not_configured", retryable=False)
        timeout = aiohttp.ClientTimeout(
            total=self.timeout_seconds,
            connect=min(5, self.timeout_seconds),
        )
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "Authorization": aiohttp.encode_basic_auth(self._agent_id, self._api_key),
                "User-Agent": "garment-buro-backend/1",
            },
        )

    async def shutdown(self) -> None:
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None

    async def create_payout(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaPayoutHttpResponse:
        self._validate_idempotence_key(idempotence_key)
        if not 1 <= len(request_body) <= MAX_YOOKASSA_PAYOUT_RESPONSE_BYTES:
            raise YooKassaPayoutProviderError(
                "invalid_request_size",
                retryable=False,
                rejected=True,
            )
        return await self._request(
            "POST",
            "/payouts",
            idempotence_key=idempotence_key,
            request_body=request_body,
        )

    async def get_payout(self, provider_payout_id: str) -> YooKassaPayoutHttpResponse:
        normalized = provider_payout_id.strip()
        if not PAYOUT_ID_PATTERN.fullmatch(normalized):
            raise YooKassaPayoutProviderError(
                "invalid_payout_id",
                retryable=False,
                rejected=True,
            )
        return await self._request("GET", f"/payouts/{normalized}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        idempotence_key: str | None = None,
        request_body: bytes | None = None,
    ) -> YooKassaPayoutHttpResponse:
        if self._session is None:
            await self.startup()
        if self._session is None:
            raise YooKassaPayoutProviderError("not_configured", retryable=False)
        headers: dict[str, str] = {}
        if idempotence_key is not None:
            headers = {
                "Content-Type": "application/json",
                "Idempotence-Key": idempotence_key,
            }
        try:
            async with self._session.request(
                method,
                f"{self.base_url}{path}",
                data=request_body,
                headers=headers,
                allow_redirects=False,
            ) as response:
                body = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_YOOKASSA_PAYOUT_RESPONSE_BYTES:
                        raise YooKassaPayoutProviderError(
                            "response_too_large",
                            retryable=True,
                            outcome_unknown=method == "POST",
                        )
                return YooKassaPayoutHttpResponse(status=response.status, body=bytes(body))
        except YooKassaPayoutProviderError:
            raise
        except TimeoutError as error:
            raise YooKassaPayoutProviderError(
                "timeout",
                retryable=True,
                outcome_unknown=method == "POST",
            ) from error
        except aiohttp.ClientError as error:
            raise YooKassaPayoutProviderError(
                "network",
                retryable=True,
                outcome_unknown=method == "POST",
            ) from error

    @staticmethod
    def _validate_idempotence_key(value: str) -> None:
        try:
            parsed = uuid.UUID(value)
        except (AttributeError, TypeError, ValueError) as error:
            raise YooKassaPayoutProviderError(
                "invalid_idempotence_key",
                retryable=False,
                rejected=True,
            ) from error
        if parsed.version != 4 or str(parsed) != value:
            raise YooKassaPayoutProviderError(
                "invalid_idempotence_key",
                retryable=False,
                rejected=True,
            )


class YooKassaPayoutProviderClient:
    def __init__(self, transport: YooKassaPayoutHttpTransport) -> None:
        self.transport = transport

    async def create_payout(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaPayoutResponse:
        response = await self.transport.create_payout(
            idempotence_key=idempotence_key,
            request_body=request_body,
        )
        return self._parse_response(response, mutation=True)

    async def get_payout(self, provider_payout_id: str) -> YooKassaPayoutResponse:
        response = await self.transport.get_payout(provider_payout_id)
        return self._parse_response(response, mutation=False)

    @staticmethod
    def _parse_response(
        response: YooKassaPayoutHttpResponse,
        *,
        mutation: bool,
    ) -> YooKassaPayoutResponse:
        if response.status == 200:
            try:
                return YooKassaPayoutResponse.model_validate_json(response.body)
            except (ValidationError, ValueError) as error:
                raise YooKassaPayoutProviderError(
                    "invalid_response",
                    retryable=True,
                    outcome_unknown=mutation,
                ) from error
        if response.status == 404 and not mutation:
            raise YooKassaPayoutProviderError(
                "payout_not_found",
                retryable=False,
                rejected=True,
            )
        if response.status in {401, 403}:
            raise YooKassaPayoutProviderError("authentication", retryable=False)
        if response.status == 429:
            raise YooKassaPayoutProviderError(
                "rate_limited",
                retryable=True,
                outcome_unknown=mutation,
            )
        if 500 <= response.status <= 599:
            raise YooKassaPayoutProviderError(
                "unavailable",
                retryable=True,
                outcome_unknown=mutation,
            )
        if 400 <= response.status <= 499:
            raise YooKassaPayoutProviderError("request_rejected", retryable=False)
        raise YooKassaPayoutProviderError(
            "unexpected_status",
            retryable=True,
            outcome_unknown=mutation,
        )
