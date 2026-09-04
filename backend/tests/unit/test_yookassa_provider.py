from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.core.config import Settings
from app.modules.payments.provider import (
    AiohttpYooKassaTransport,
    YooKassaHttpResponse,
    YooKassaProviderClient,
    YooKassaProviderError,
)


def _payment_body(*, status: str = "pending") -> bytes:
    payload: dict[str, object] = {
        "id": "2c111111-000f-5000-a000-111111111111",
        "status": status,
        "amount": {"value": "125.50", "currency": "RUB"},
        "metadata": {"order_id": "17"},
        "payment_method": {"type": "bank_card", "title": "Bank card *0000"},
        "paid": status in {"waiting_for_capture", "succeeded"},
        "test": True,
        "created_at": "2026-08-11T12:00:00Z",
        "ignored_customer_evidence": "must-not-leak",
    }
    if status == "pending":
        payload["confirmation"] = {
            "type": "redirect",
            "confirmation_url": "https://yoomoney.ru/checkout/payment/1",
        }
    if status == "succeeded":
        payload["captured_at"] = "2026-08-11T12:01:00Z"
    if status == "canceled":
        payload["cancellation_details"] = {
            "party": "yoo_money",
            "reason": "payment_expired",
        }
    return json.dumps(payload).encode()


@dataclass
class FakeTransport:
    response: YooKassaHttpResponse
    calls: list[str]

    async def get_payment(self, provider_payment_id: str) -> YooKassaHttpResponse:
        self.calls.append(provider_payment_id)
        return self.response


@dataclass
class FakeCreateTransport:
    response: YooKassaHttpResponse
    calls: list[tuple[str, bytes]]

    async def create_payment(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaHttpResponse:
        self.calls.append((idempotence_key, request_body))
        return self.response

    async def get_payment(self, provider_payment_id: str) -> YooKassaHttpResponse:
        raise AssertionError(f"Unexpected GET for {provider_payment_id}")


@dataclass
class FakeMutationTransport:
    response: YooKassaHttpResponse
    calls: list[tuple[str, str, str, bytes | None]]

    async def capture_payment(
        self,
        provider_payment_id: str,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaHttpResponse:
        self.calls.append(("capture", provider_payment_id, idempotence_key, request_body))
        return self.response

    async def cancel_payment(
        self,
        provider_payment_id: str,
        *,
        idempotence_key: str,
    ) -> YooKassaHttpResponse:
        self.calls.append(("cancel", provider_payment_id, idempotence_key, None))
        return self.response


class FakeResponseContent:
    def __init__(self, body: bytes) -> None:
        self.body = body

    async def iter_chunked(self, size: int):
        del size
        yield self.body


class FakeResponseContext:
    def __init__(self, *, status: int, body: bytes) -> None:
        self.status = status
        self.content = FakeResponseContent(body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeAiohttpSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponseContext:
        self.calls.append((url, kwargs))
        return FakeResponseContext(status=200, body=_payment_body())


def test_provider_client_maps_a_safe_typed_snapshot() -> None:
    async def scenario() -> None:
        transport = FakeTransport(
            YooKassaHttpResponse(status=200, body=_payment_body(status="succeeded")),
            [],
        )
        snapshot = await YooKassaProviderClient(transport).get_payment(
            "2c111111-000f-5000-a000-111111111111"
        )

        assert transport.calls == ["2c111111-000f-5000-a000-111111111111"]
        assert snapshot.status == "succeeded" and snapshot.paid
        assert snapshot.metadata_order_id == 17
        assert str(snapshot.amount) == "125.50"
        assert snapshot.payment_method == "bank_card"
        assert "must-not-leak" not in repr(snapshot)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status", "code", "retryable", "rejected"),
    [
        (404, "payment_not_found", False, True),
        (401, "authentication", False, False),
        (403, "authentication", False, False),
        (429, "rate_limited", True, False),
        (500, "unavailable", True, False),
        (503, "unavailable", True, False),
        (400, "request_rejected", False, False),
        (302, "unexpected_status", True, False),
    ],
)
def test_provider_client_classifies_http_failures(
    status: int,
    code: str,
    retryable: bool,
    rejected: bool,
) -> None:
    async def scenario() -> None:
        client = YooKassaProviderClient(
            FakeTransport(YooKassaHttpResponse(status=status, body=b"sensitive-body"), [])
        )
        with pytest.raises(YooKassaProviderError) as captured:
            await client.get_payment("2c111111-000f-5000-a000-111111111111")
        assert captured.value.code == code
        assert captured.value.retryable is retryable
        assert captured.value.rejected is rejected
        assert "sensitive-body" not in str(captured.value)

    asyncio.run(scenario())


def test_provider_client_retries_malformed_success_without_exposing_body() -> None:
    async def scenario() -> None:
        client = YooKassaProviderClient(
            FakeTransport(
                YooKassaHttpResponse(status=200, body=b'{"secret":"malformed"}'),
                [],
            )
        )
        with pytest.raises(YooKassaProviderError) as captured:
            await client.get_payment("2c111111-000f-5000-a000-111111111111")
        assert captured.value.code == "invalid_response" and captured.value.retryable
        assert "malformed" not in str(captured.value)

    asyncio.run(scenario())


def test_provider_client_creates_with_typed_snapshot_and_exact_request() -> None:
    async def scenario() -> None:
        body = b'{"amount":{"currency":"RUB","value":"125.50"}}'
        transport = FakeCreateTransport(
            YooKassaHttpResponse(status=200, body=_payment_body()),
            [],
        )
        snapshot = await YooKassaProviderClient(transport).create_payment(
            idempotence_key="00000000-0000-4000-8000-000000000001",
            request_body=body,
        )

        assert transport.calls == [("00000000-0000-4000-8000-000000000001", body)]
        assert snapshot.status == "pending"
        assert snapshot.metadata_order_id == 17
        assert snapshot.confirmation_url == "https://yoomoney.ru/checkout/payment/1"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status", "code", "outcome_unknown"),
    [
        (400, "request_rejected", False),
        (401, "authentication", False),
        (403, "authentication", False),
        (404, "request_rejected", False),
        (429, "rate_limited", True),
        (500, "unavailable", True),
        (503, "unavailable", True),
        (302, "unexpected_status", True),
    ],
)
def test_provider_client_classifies_creation_outcome(
    status: int,
    code: str,
    outcome_unknown: bool,
) -> None:
    async def scenario() -> None:
        client = YooKassaProviderClient(
            FakeCreateTransport(
                YooKassaHttpResponse(status=status, body=b'{"secret":"not-logged"}'),
                [],
            )
        )
        with pytest.raises(YooKassaProviderError) as captured:
            await client.create_payment(
                idempotence_key="00000000-0000-4000-8000-000000000001",
                request_body=b"{}",
            )
        assert captured.value.code == code
        assert captured.value.outcome_unknown is outcome_unknown
        assert "not-logged" not in str(captured.value)

    asyncio.run(scenario())


def test_aiohttp_creation_transport_sends_safe_headers_and_no_redirects() -> None:
    async def scenario() -> None:
        session = FakeAiohttpSession()
        transport = AiohttpYooKassaTransport(
            Settings(
                _env_file=None,
                yookassa_shop_id="shop",
                yookassa_api_key="secret",
            ),
            session=session,
        )
        request_body = b'{"safe":"body"}'
        response = await transport.create_payment(
            idempotence_key="00000000-0000-4000-8000-000000000001",
            request_body=request_body,
        )
        assert response.status == 200
        assert len(session.calls) == 1
        url, kwargs = session.calls[0]
        assert url == "https://api.yookassa.ru/v3/payments"
        assert kwargs["data"] == request_body
        assert kwargs["allow_redirects"] is False
        assert kwargs["headers"] == {
            "Content-Type": "application/json",
            "Idempotence-Key": "00000000-0000-4000-8000-000000000001",
        }

        with pytest.raises(YooKassaProviderError) as invalid_key:
            await transport.create_payment(
                idempotence_key="not-a-uuid",
                request_body=request_body,
            )
        assert invalid_key.value.code == "invalid_idempotence_key"
        assert len(session.calls) == 1

        with pytest.raises(YooKassaProviderError) as empty_body:
            await transport.create_payment(
                idempotence_key="00000000-0000-4000-8000-000000000001",
                request_body=b"",
            )
        assert empty_body.value.code == "invalid_request_size"
        assert len(session.calls) == 1

    asyncio.run(scenario())


def test_provider_client_capture_and_cancel_use_typed_mutations() -> None:
    async def scenario() -> None:
        key = "00000000-0000-4000-8000-000000000001"
        provider_id = "2c111111-000f-5000-a000-111111111111"
        capture_transport = FakeMutationTransport(
            YooKassaHttpResponse(status=200, body=_payment_body(status="succeeded")),
            [],
        )
        captured = await YooKassaProviderClient(capture_transport).capture_payment(
            provider_id,
            idempotence_key=key,
            request_body=b"{}",
        )
        assert captured.status == "succeeded"
        assert capture_transport.calls == [("capture", provider_id, key, b"{}")]

        cancel_transport = FakeMutationTransport(
            YooKassaHttpResponse(status=200, body=_payment_body(status="canceled")),
            [],
        )
        canceled = await YooKassaProviderClient(cancel_transport).cancel_payment(
            provider_id,
            idempotence_key=key,
        )
        assert canceled.status == "canceled"
        assert cancel_transport.calls == [("cancel", provider_id, key, None)]

    asyncio.run(scenario())


def test_aiohttp_mutation_transport_matches_yookassa_paths_and_bodies() -> None:
    async def scenario() -> None:
        session = FakeAiohttpSession()
        transport = AiohttpYooKassaTransport(
            Settings(
                _env_file=None,
                yookassa_shop_id="shop",
                yookassa_api_key="secret",
            ),
            session=session,
        )
        key = "00000000-0000-4000-8000-000000000001"
        provider_id = "2c111111-000f-5000-a000-111111111111"

        await transport.capture_payment(
            provider_id,
            idempotence_key=key,
            request_body=b"{}",
        )
        await transport.cancel_payment(provider_id, idempotence_key=key)

        capture_url, capture_kwargs = session.calls[0]
        assert capture_url.endswith(f"/payments/{provider_id}/capture")
        assert capture_kwargs["data"] == b"{}"
        assert capture_kwargs["headers"] == {
            "Idempotence-Key": key,
            "Content-Type": "application/json",
        }
        cancel_url, cancel_kwargs = session.calls[1]
        assert cancel_url.endswith(f"/payments/{provider_id}/cancel")
        assert cancel_kwargs["data"] is None
        assert cancel_kwargs["headers"] == {"Idempotence-Key": key}

    asyncio.run(scenario())


def test_aiohttp_transport_fails_closed_before_network() -> None:
    async def scenario() -> None:
        settings = Settings(_env_file=None, yookassa_shop_id=None, yookassa_api_key=None)
        transport = AiohttpYooKassaTransport(settings)
        with pytest.raises(YooKassaProviderError) as unconfigured:
            await transport.startup()
        assert unconfigured.value.code == "not_configured"

        configured = AiohttpYooKassaTransport(
            Settings(
                _env_file=None,
                yookassa_shop_id="shop",
                yookassa_api_key="secret",
            )
        )
        with pytest.raises(YooKassaProviderError) as invalid_id:
            await configured.get_payment("../credentials")
        assert invalid_id.value.code == "invalid_payment_id"
        assert invalid_id.value.rejected
        await configured.shutdown()

    asyncio.run(scenario())


def test_refactored_provider_does_not_use_sdk_global_configuration() -> None:
    source = (Path(__file__).resolve().parents[2] / "app/modules/payments/provider.py").read_text(
        encoding="utf-8"
    )

    assert "Configuration.configure" not in source
    assert "from yookassa" not in source
