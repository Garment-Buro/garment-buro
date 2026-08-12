from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Protocol

import aiohttp
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.payments.schemas import ProviderPaymentSnapshot, YooKassaWebhookPayment

MAX_YOOKASSA_RESPONSE_BYTES = 256 * 1024
PROVIDER_PAYMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,255}$")


class YooKassaProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        rejected: bool = False,
        outcome_unknown: bool = False,
    ) -> None:
        super().__init__(f"YooKassa provider error: {code}")
        self.code = code
        self.retryable = retryable
        self.rejected = rejected
        self.outcome_unknown = outcome_unknown


@dataclass(frozen=True, slots=True)
class YooKassaHttpResponse:
    status: int
    body: bytes


class YooKassaHttpTransport(Protocol):
    async def get_payment(self, provider_payment_id: str) -> YooKassaHttpResponse: ...

    async def create_payment(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaHttpResponse: ...


class YooKassaProvider(Protocol):
    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot: ...

    async def create_payment(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> ProviderPaymentSnapshot: ...


class AiohttpYooKassaTransport:
    """Instance-scoped YooKassa HTTP transport without SDK-global configuration."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.base_url = settings.yookassa_api_url.rstrip("/")
        self._shop_id = Settings.secret_value(settings.yookassa_shop_id)
        self._api_key = Settings.secret_value(settings.yookassa_api_key)
        self.timeout_seconds = settings.yookassa_timeout_seconds
        self._session = session
        self._owns_session = session is None

    async def startup(self) -> None:
        if self._session is not None:
            return
        if not self._shop_id or not self._api_key:
            raise YooKassaProviderError("not_configured", retryable=False)
        timeout = aiohttp.ClientTimeout(
            total=self.timeout_seconds,
            connect=min(5, self.timeout_seconds),
        )
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "Authorization": aiohttp.encode_basic_auth(self._shop_id, self._api_key),
                "User-Agent": "garment-buro-backend/1",
            },
        )

    async def shutdown(self) -> None:
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None

    async def get_payment(self, provider_payment_id: str) -> YooKassaHttpResponse:
        normalized = provider_payment_id.strip()
        if not PROVIDER_PAYMENT_ID_PATTERN.fullmatch(normalized):
            raise YooKassaProviderError(
                "invalid_payment_id",
                retryable=False,
                rejected=True,
            )
        if self._session is None:
            await self.startup()
        if self._session is None:
            raise YooKassaProviderError("not_configured", retryable=False)
        try:
            async with self._session.get(
                f"{self.base_url}/payments/{normalized}",
                allow_redirects=False,
            ) as response:
                body = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_YOOKASSA_RESPONSE_BYTES:
                        raise YooKassaProviderError(
                            "response_too_large",
                            retryable=False,
                        )
                return YooKassaHttpResponse(status=response.status, body=bytes(body))
        except YooKassaProviderError:
            raise
        except TimeoutError as error:
            raise YooKassaProviderError(
                "timeout",
                retryable=True,
                outcome_unknown=True,
            ) from error
        except aiohttp.ClientError as error:
            raise YooKassaProviderError(
                "network",
                retryable=True,
                outcome_unknown=True,
            ) from error

    async def create_payment(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaHttpResponse:
        try:
            parsed_key = uuid.UUID(idempotence_key)
        except (AttributeError, TypeError, ValueError) as error:
            raise YooKassaProviderError(
                "invalid_idempotence_key",
                retryable=False,
                rejected=True,
            ) from error
        if parsed_key.version != 4 or str(parsed_key) != idempotence_key:
            raise YooKassaProviderError(
                "invalid_idempotence_key",
                retryable=False,
                rejected=True,
            )
        if not 1 <= len(request_body) <= MAX_YOOKASSA_RESPONSE_BYTES:
            raise YooKassaProviderError(
                "invalid_request_size",
                retryable=False,
                rejected=True,
            )
        if self._session is None:
            await self.startup()
        if self._session is None:
            raise YooKassaProviderError("not_configured", retryable=False)
        try:
            async with self._session.post(
                f"{self.base_url}/payments",
                data=request_body,
                headers={
                    "Content-Type": "application/json",
                    "Idempotence-Key": idempotence_key,
                },
                allow_redirects=False,
            ) as response:
                body = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_YOOKASSA_RESPONSE_BYTES:
                        raise YooKassaProviderError(
                            "response_too_large",
                            retryable=True,
                            outcome_unknown=True,
                        )
                return YooKassaHttpResponse(status=response.status, body=bytes(body))
        except YooKassaProviderError:
            raise
        except TimeoutError as error:
            raise YooKassaProviderError(
                "timeout",
                retryable=True,
                outcome_unknown=True,
            ) from error
        except aiohttp.ClientError as error:
            raise YooKassaProviderError(
                "network",
                retryable=True,
                outcome_unknown=True,
            ) from error


class YooKassaProviderClient:
    def __init__(self, transport: YooKassaHttpTransport) -> None:
        self.transport = transport

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        response = await self.transport.get_payment(provider_payment_id)
        if response.status == 200:
            try:
                return YooKassaWebhookPayment.model_validate_json(response.body).to_snapshot()
            except (ValidationError, ValueError) as error:
                raise YooKassaProviderError("invalid_response", retryable=True) from error
        if response.status == 404:
            raise YooKassaProviderError(
                "payment_not_found",
                retryable=False,
                rejected=True,
            )
        if response.status in {401, 403}:
            raise YooKassaProviderError("authentication", retryable=False)
        if response.status == 429:
            raise YooKassaProviderError("rate_limited", retryable=True)
        if 500 <= response.status <= 599:
            raise YooKassaProviderError("unavailable", retryable=True)
        if 400 <= response.status <= 499:
            raise YooKassaProviderError("request_rejected", retryable=False)
        raise YooKassaProviderError("unexpected_status", retryable=True)

    async def create_payment(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> ProviderPaymentSnapshot:
        response = await self.transport.create_payment(
            idempotence_key=idempotence_key,
            request_body=request_body,
        )
        if response.status == 200:
            try:
                return YooKassaWebhookPayment.model_validate_json(response.body).to_snapshot()
            except (ValidationError, ValueError) as error:
                raise YooKassaProviderError(
                    "invalid_response",
                    retryable=True,
                    outcome_unknown=True,
                ) from error
        if response.status in {401, 403}:
            raise YooKassaProviderError("authentication", retryable=False)
        if response.status == 429:
            raise YooKassaProviderError(
                "rate_limited",
                retryable=True,
                outcome_unknown=True,
            )
        if 500 <= response.status <= 599:
            raise YooKassaProviderError(
                "unavailable",
                retryable=True,
                outcome_unknown=True,
            )
        if 400 <= response.status <= 499:
            raise YooKassaProviderError("request_rejected", retryable=False)
        raise YooKassaProviderError(
            "unexpected_status",
            retryable=True,
            outcome_unknown=True,
        )
