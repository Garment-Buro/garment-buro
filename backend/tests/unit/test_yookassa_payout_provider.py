from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import pytest

from app.core.config import Settings
from app.modules.payouts.provider import (
    AiohttpYooKassaPayoutTransport,
    YooKassaPayoutHttpResponse,
    YooKassaPayoutProviderClient,
    YooKassaPayoutProviderError,
)

PROVIDER_PAYOUT_ID = "po-" + "1" * 33


def _body(*, status: str = "pending") -> bytes:
    payload: dict[str, object] = {
        "id": PROVIDER_PAYOUT_ID,
        "amount": {"value": "500.00", "currency": "RUB"},
        "status": status,
        "payout_destination": {
            "type": "bank_card",
            "card": {"first6": "555555", "last4": "4477", "card_type": "MasterCard"},
        },
        "description": "Выплата по заказу 17",
        "created_at": "2026-09-04T12:00:00Z",
        "metadata": {"internal_payout_id": "1", "reference": "order:17"},
        "test": True,
        "ignored_secret": "must-not-leak",
    }
    if status == "succeeded":
        payload["succeeded_at"] = "2026-09-04T12:01:00Z"
    return json.dumps(payload).encode()


@dataclass
class FakeTransport:
    response: YooKassaPayoutHttpResponse
    calls: list[tuple[str, str | bytes]]

    async def create_payout(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaPayoutHttpResponse:
        self.calls.append((idempotence_key, request_body))
        return self.response

    async def get_payout(self, provider_payout_id: str) -> YooKassaPayoutHttpResponse:
        self.calls.append(("get", provider_payout_id))
        return self.response


class FakeResponseContent:
    def __init__(self, body: bytes) -> None:
        self.body = body

    async def iter_chunked(self, size: int):
        del size
        yield self.body


class FakeResponseContext:
    def __init__(self, body: bytes) -> None:
        self.status = 200
        self.content = FakeResponseContent(body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponseContext:
        self.calls.append((method, url, kwargs))
        return FakeResponseContext(_body())


def test_payout_provider_maps_only_validated_evidence() -> None:
    async def scenario() -> None:
        transport = FakeTransport(YooKassaPayoutHttpResponse(200, _body()), [])
        snapshot = await YooKassaPayoutProviderClient(transport).create_payout(
            idempotence_key="00000000-0000-4000-8000-000000000001",
            request_body=b"{}",
        )
        assert snapshot.status == "pending"
        assert snapshot.metadata.internal_payout_id == 1
        assert "must-not-leak" not in repr(snapshot)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status", "code", "outcome_unknown"),
    [
        (400, "request_rejected", False),
        (401, "authentication", False),
        (429, "rate_limited", True),
        (500, "unavailable", True),
    ],
)
def test_payout_provider_classifies_creation_failures(
    status: int,
    code: str,
    outcome_unknown: bool,
) -> None:
    async def scenario() -> None:
        transport = FakeTransport(YooKassaPayoutHttpResponse(status, b"sensitive"), [])
        with pytest.raises(YooKassaPayoutProviderError) as captured:
            await YooKassaPayoutProviderClient(transport).create_payout(
                idempotence_key="00000000-0000-4000-8000-000000000001",
                request_body=b"{}",
            )
        assert captured.value.code == code
        assert captured.value.outcome_unknown is outcome_unknown
        assert "sensitive" not in str(captured.value)

    asyncio.run(scenario())


def test_payout_transport_uses_payout_resource_and_idempotence_header() -> None:
    async def scenario() -> None:
        session = FakeSession()
        transport = AiohttpYooKassaPayoutTransport(
            Settings(
                _env_file=None,
                yookassa_payout_agent_id="agent-id",
                yookassa_payout_api_key="payout-secret",
            ),
            session=session,
        )
        key = "00000000-0000-4000-8000-000000000001"
        response = await transport.create_payout(idempotence_key=key, request_body=b"{}")
        assert response.status == 200
        assert session.calls == [
            (
                "POST",
                "https://api.yookassa.ru/v3/payouts",
                {
                    "data": b"{}",
                    "headers": {
                        "Content-Type": "application/json",
                        "Idempotence-Key": key,
                    },
                    "allow_redirects": False,
                },
            )
        ]

        with pytest.raises(YooKassaPayoutProviderError):
            await transport.get_payout("../secret")
        assert len(session.calls) == 1

    asyncio.run(scenario())
