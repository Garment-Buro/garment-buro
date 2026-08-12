from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Protocol

import aiohttp

from app.core.config import Settings

MAX_CDEK_RESPONSE_BYTES = 256 * 1024
MAX_CDEK_REQUEST_BYTES = 512 * 1024
SAFE_PROVIDER_REFERENCE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class CdekProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        rejected: bool = False,
        outcome_unknown: bool = False,
        provider_uuid: str | None = None,
    ) -> None:
        super().__init__(f"CDEK provider error: {code}")
        self.code = code
        self.retryable = retryable
        self.rejected = rejected
        self.outcome_unknown = outcome_unknown
        self.provider_uuid = provider_uuid


@dataclass(frozen=True, slots=True)
class CdekHttpResponse:
    status: int
    body: bytes


@dataclass(frozen=True, slots=True)
class CdekOrderSnapshot:
    provider_uuid: str
    client_order_number: str | None = None
    cdek_number: str | None = None
    status_code: str | None = None
    status_name: str | None = None


@dataclass(frozen=True, slots=True)
class CdekTariffQuote:
    delivery_sum: Decimal
    period_min: int | None = None
    period_max: int | None = None


class CdekHttpTransport(Protocol):
    async def calculate_tariff(self, request_body: bytes) -> CdekHttpResponse: ...

    async def create_order(self, request_body: bytes) -> CdekHttpResponse: ...

    async def get_order(self, provider_uuid: str) -> CdekHttpResponse: ...


class CdekProvider(Protocol):
    async def create_order(self, request_body: bytes) -> CdekOrderSnapshot: ...

    async def get_order(self, provider_uuid: str) -> CdekOrderSnapshot: ...


class CdekQuoteProvider(Protocol):
    async def calculate_tariff(self, request_body: bytes) -> CdekTariffQuote: ...


class AiohttpCdekTransport:
    """Instance-scoped CDEK v2 transport with a synchronized OAuth token cache."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.base_url = settings.cdek_api_url.rstrip("/")
        self._client_id = Settings.secret_value(settings.cdek_client_id)
        self._client_secret = Settings.secret_value(settings.cdek_client_secret)
        self.timeout_seconds = settings.cdek_timeout_seconds
        self._session = session
        self._owns_session = session is None
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    async def startup(self) -> None:
        if self._session is not None:
            return
        if not self._client_id or not self._client_secret:
            raise CdekProviderError("not_configured", retryable=False)
        timeout = aiohttp.ClientTimeout(
            total=self.timeout_seconds,
            connect=min(5, self.timeout_seconds),
        )
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "garment-buro-backend/1",
            },
        )

    async def shutdown(self) -> None:
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None

    async def create_order(self, request_body: bytes) -> CdekHttpResponse:
        if not 1 <= len(request_body) <= MAX_CDEK_REQUEST_BYTES:
            raise CdekProviderError(
                "invalid_request_size",
                retryable=False,
                rejected=True,
            )
        token = await self._access_token()
        session = await self._require_session()
        try:
            async with session.post(
                f"{self.base_url}/orders",
                data=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                allow_redirects=False,
            ) as response:
                return CdekHttpResponse(
                    status=response.status,
                    body=await self._read_limited(response, outcome_unknown=True),
                )
        except CdekProviderError:
            raise
        except TimeoutError as error:
            raise CdekProviderError(
                "timeout",
                retryable=True,
                outcome_unknown=True,
            ) from error
        except aiohttp.ClientError as error:
            raise CdekProviderError(
                "network",
                retryable=True,
                outcome_unknown=True,
            ) from error

    async def calculate_tariff(self, request_body: bytes) -> CdekHttpResponse:
        if not 1 <= len(request_body) <= MAX_CDEK_REQUEST_BYTES:
            raise CdekProviderError(
                "invalid_request_size",
                retryable=False,
                rejected=True,
            )
        token = await self._access_token()
        session = await self._require_session()
        try:
            async with session.post(
                f"{self.base_url}/calculator/tariff",
                data=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                allow_redirects=False,
            ) as response:
                return CdekHttpResponse(
                    status=response.status,
                    body=await self._read_limited(response, outcome_unknown=False),
                )
        except CdekProviderError:
            raise
        except TimeoutError as error:
            raise CdekProviderError("timeout", retryable=True) from error
        except aiohttp.ClientError as error:
            raise CdekProviderError("network", retryable=True) from error

    async def get_order(self, provider_uuid: str) -> CdekHttpResponse:
        normalized = _safe_reference(provider_uuid, "invalid_provider_uuid")
        token = await self._access_token()
        session = await self._require_session()
        try:
            async with session.get(
                f"{self.base_url}/orders/{normalized}",
                headers={"Authorization": f"Bearer {token}"},
                allow_redirects=False,
            ) as response:
                return CdekHttpResponse(
                    status=response.status,
                    body=await self._read_limited(response, outcome_unknown=False),
                )
        except CdekProviderError:
            raise
        except TimeoutError as error:
            raise CdekProviderError("timeout", retryable=True) from error
        except aiohttp.ClientError as error:
            raise CdekProviderError("network", retryable=True) from error

    async def _access_token(self) -> str:
        now = time.monotonic()
        if self._token and now < self._token_expires_at:
            return self._token
        async with self._token_lock:
            now = time.monotonic()
            if self._token and now < self._token_expires_at:
                return self._token
            if not self._client_id or not self._client_secret:
                raise CdekProviderError("not_configured", retryable=False)
            session = await self._require_session()
            try:
                async with session.post(
                    f"{self.base_url}/oauth/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    allow_redirects=False,
                ) as response:
                    body = await self._read_limited(response, outcome_unknown=False)
                    if response.status != 200:
                        self._raise_token_status(response.status)
            except CdekProviderError:
                raise
            except TimeoutError as error:
                raise CdekProviderError("oauth_timeout", retryable=True) from error
            except aiohttp.ClientError as error:
                raise CdekProviderError("oauth_network", retryable=True) from error
            payload = _json_object(body, code="oauth_invalid_response", outcome_unknown=False)
            token = payload.get("access_token")
            expires_in = payload.get("expires_in")
            if not isinstance(token, str) or not token or len(token) > 8_192:
                raise CdekProviderError("oauth_invalid_response", retryable=True)
            if not isinstance(expires_in, int) or not 1 <= expires_in <= 86_400:
                raise CdekProviderError("oauth_invalid_response", retryable=True)
            self._token = token
            self._token_expires_at = time.monotonic() + max(1, expires_in - 10)
            return token

    async def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            await self.startup()
        if self._session is None:
            raise CdekProviderError("not_configured", retryable=False)
        return self._session

    @staticmethod
    async def _read_limited(
        response: aiohttp.ClientResponse,
        *,
        outcome_unknown: bool,
    ) -> bytes:
        body = bytearray()
        async for chunk in response.content.iter_chunked(64 * 1024):
            body.extend(chunk)
            if len(body) > MAX_CDEK_RESPONSE_BYTES:
                raise CdekProviderError(
                    "response_too_large",
                    retryable=True,
                    outcome_unknown=outcome_unknown,
                )
        return bytes(body)

    @staticmethod
    def _raise_token_status(status: int) -> None:
        if status in {400, 401, 403}:
            raise CdekProviderError("authentication", retryable=False)
        if status == 429 or 500 <= status <= 599:
            raise CdekProviderError("oauth_unavailable", retryable=True)
        raise CdekProviderError("oauth_unexpected_status", retryable=True)


class CdekProviderClient:
    def __init__(self, transport: CdekHttpTransport) -> None:
        self.transport = transport

    async def calculate_tariff(self, request_body: bytes) -> CdekTariffQuote:
        response = await self.transport.calculate_tariff(request_body)
        if response.status == 200:
            payload = _json_object(
                response.body,
                code="invalid_quote_response",
                outcome_unknown=False,
            )
            if _request_errors(payload):
                raise CdekProviderError(
                    "request_rejected",
                    retryable=False,
                    rejected=True,
                )
            delivery_sum = _quote_money(payload.get("delivery_sum"))
            period_min = _quote_period(payload.get("period_min"))
            period_max = _quote_period(payload.get("period_max"))
            if period_min is not None and period_max is not None and period_min > period_max:
                raise CdekProviderError("invalid_quote_response", retryable=True)
            return CdekTariffQuote(
                delivery_sum=delivery_sum,
                period_min=period_min,
                period_max=period_max,
            )
        if response.status in {401, 403}:
            raise CdekProviderError("authentication", retryable=False)
        if response.status == 429:
            raise CdekProviderError("rate_limited", retryable=True)
        if 500 <= response.status <= 599:
            raise CdekProviderError("unavailable", retryable=True)
        if 400 <= response.status <= 499:
            raise CdekProviderError("request_rejected", retryable=False, rejected=True)
        raise CdekProviderError("unexpected_status", retryable=True)

    async def create_order(self, request_body: bytes) -> CdekOrderSnapshot:
        response = await self.transport.create_order(request_body)
        if 200 <= response.status <= 299:
            try:
                payload = _json_object(
                    response.body,
                    code="invalid_response",
                    outcome_unknown=True,
                )
                provider_uuid = _optional_entity_uuid(payload)
                if _request_errors(payload):
                    raise CdekProviderError(
                        "request_rejected",
                        retryable=False,
                        rejected=True,
                        provider_uuid=provider_uuid,
                    )
                if provider_uuid is None:
                    raise CdekProviderError(
                        "invalid_response",
                        retryable=True,
                        outcome_unknown=True,
                    )
                return _snapshot(payload, expected_uuid=provider_uuid)
            except CdekProviderError as error:
                if error.rejected or error.outcome_unknown:
                    raise
                raise CdekProviderError(
                    error.code,
                    retryable=True,
                    outcome_unknown=True,
                    provider_uuid=error.provider_uuid,
                ) from error
            except (TypeError, ValueError) as error:
                raise CdekProviderError(
                    "invalid_response",
                    retryable=True,
                    outcome_unknown=True,
                ) from error
        if response.status in {401, 403}:
            raise CdekProviderError("authentication", retryable=False)
        if response.status == 429:
            raise CdekProviderError(
                "rate_limited",
                retryable=True,
                outcome_unknown=True,
            )
        if 500 <= response.status <= 599:
            raise CdekProviderError(
                "unavailable",
                retryable=True,
                outcome_unknown=True,
            )
        if 400 <= response.status <= 499:
            raise CdekProviderError("request_rejected", retryable=False, rejected=True)
        raise CdekProviderError(
            "unexpected_status",
            retryable=True,
            outcome_unknown=True,
        )

    async def get_order(self, provider_uuid: str) -> CdekOrderSnapshot:
        response = await self.transport.get_order(provider_uuid)
        if response.status == 200:
            payload = _json_object(
                response.body,
                code="invalid_response",
                outcome_unknown=False,
            )
            try:
                return _snapshot(payload, expected_uuid=provider_uuid)
            except CdekProviderError as error:
                raise CdekProviderError("invalid_response", retryable=True) from error
        if response.status == 404:
            raise CdekProviderError("order_not_found", retryable=False, rejected=True)
        if response.status in {401, 403}:
            raise CdekProviderError("authentication", retryable=False)
        if response.status == 429 or 500 <= response.status <= 599:
            raise CdekProviderError("unavailable", retryable=True)
        if 400 <= response.status <= 499:
            raise CdekProviderError("request_rejected", retryable=False, rejected=True)
        raise CdekProviderError("unexpected_status", retryable=True)


def _json_object(body: bytes, *, code: str, outcome_unknown: bool) -> dict[str, object]:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CdekProviderError(
            code,
            retryable=True,
            outcome_unknown=outcome_unknown,
        ) from error
    if not isinstance(payload, dict):
        raise CdekProviderError(
            code,
            retryable=True,
            outcome_unknown=outcome_unknown,
        )
    return payload


def _quote_money(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise CdekProviderError("invalid_quote_response", retryable=True)
    try:
        normalized = Decimal(str(value))
        if not normalized.is_finite() or not Decimal("0") <= normalized <= Decimal("999999999.99"):
            raise CdekProviderError("invalid_quote_response", retryable=True)
        return normalized.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise CdekProviderError("invalid_quote_response", retryable=True) from error


def _quote_period(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3_650:
        raise CdekProviderError("invalid_quote_response", retryable=True)
    return value


def _optional_entity_uuid(payload: dict[str, object]) -> str | None:
    entity = payload.get("entity")
    if not isinstance(entity, dict):
        return None
    try:
        return _safe_reference(entity.get("uuid"), "invalid_response")
    except CdekProviderError as error:
        raise CdekProviderError(
            "invalid_response",
            retryable=True,
            outcome_unknown=True,
        ) from error


def _request_errors(payload: dict[str, object]) -> bool:
    if isinstance(payload.get("error"), str):
        return True
    errors = payload.get("errors")
    if errors is not None:
        if not isinstance(errors, list):
            raise CdekProviderError(
                "invalid_response",
                retryable=True,
                outcome_unknown=True,
            )
        if errors:
            return True
    requests = payload.get("requests")
    if requests is None:
        return False
    if not isinstance(requests, list):
        raise CdekProviderError(
            "invalid_response",
            retryable=True,
            outcome_unknown=True,
        )
    for request in requests:
        if not isinstance(request, dict):
            raise CdekProviderError(
                "invalid_response",
                retryable=True,
                outcome_unknown=True,
            )
        request_errors = request.get("errors")
        if request_errors is not None and not isinstance(request_errors, list):
            raise CdekProviderError(
                "invalid_response",
                retryable=True,
                outcome_unknown=True,
            )
        if request.get("state") == "INVALID" or request_errors:
            return True
    return False


def _snapshot(payload: dict[str, object], *, expected_uuid: str) -> CdekOrderSnapshot:
    entity = payload.get("entity")
    source = entity if isinstance(entity, dict) else payload
    provider_uuid = _safe_reference(source.get("uuid"), "invalid_response")
    if provider_uuid != expected_uuid:
        raise CdekProviderError("provider_uuid_mismatch", retryable=False)
    cdek_number = _optional_reference(source.get("cdek_number"))
    client_order_number = _optional_reference(source.get("number"))
    status_code: str | None = None
    status_name: str | None = None
    statuses = source.get("statuses")
    if isinstance(statuses, list) and statuses:
        latest = statuses[-1]
        if isinstance(latest, dict):
            status_code = _optional_reference(latest.get("code"))
            name = latest.get("name")
            status_name = name.strip()[:255] if isinstance(name, str) and name.strip() else None
    return CdekOrderSnapshot(
        provider_uuid=provider_uuid,
        client_order_number=client_order_number,
        cdek_number=cdek_number,
        status_code=status_code,
        status_name=status_name,
    )


def _safe_reference(value: object, code: str) -> str:
    normalized = str(value).strip() if isinstance(value, (str, int)) else ""
    if not SAFE_PROVIDER_REFERENCE.fullmatch(normalized):
        raise CdekProviderError(code, retryable=False, rejected=True)
    return normalized


def _optional_reference(value: object) -> str | None:
    if value is None:
        return None
    return _safe_reference(value, "invalid_response")
