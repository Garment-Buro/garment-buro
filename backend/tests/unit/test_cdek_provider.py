from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.modules.delivery.provider import (
    AiohttpCdekTransport,
    CdekHttpResponse,
    CdekProviderClient,
    CdekProviderError,
)


class FakeCdekTransport:
    def __init__(
        self,
        *,
        create_response: CdekHttpResponse | None = None,
        get_response: CdekHttpResponse | None = None,
        quote_response: CdekHttpResponse | None = None,
    ) -> None:
        self.create_response = create_response
        self.get_response = get_response
        self.quote_response = quote_response
        self.created_bodies: list[bytes] = []
        self.quoted_bodies: list[bytes] = []
        self.requested_uuids: list[str] = []

    async def create_order(self, request_body: bytes) -> CdekHttpResponse:
        self.created_bodies.append(request_body)
        assert self.create_response is not None
        return self.create_response

    async def calculate_tariff(self, request_body: bytes) -> CdekHttpResponse:
        self.quoted_bodies.append(request_body)
        assert self.quote_response is not None
        return self.quote_response

    async def get_order(self, provider_uuid: str) -> CdekHttpResponse:
        self.requested_uuids.append(provider_uuid)
        assert self.get_response is not None
        return self.get_response


class FakeResponseContent:
    def __init__(self, body: bytes) -> None:
        self.body = body

    async def iter_chunked(self, size: int):
        for start in range(0, len(self.body), size):
            yield self.body[start : start + size]


class FakeAiohttpResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.content = FakeResponseContent(body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeAiohttpSession:
    def __init__(self, responses: list[FakeAiohttpResponse]) -> None:
        self.responses = list(responses)
        self.posts: list[tuple[str, object, dict[str, str], bool]] = []

    def post(self, url: str, *, data, headers: dict[str, str], allow_redirects: bool):
        self.posts.append((url, data, headers, allow_redirects))
        return self.responses.pop(0)


def _response(status: int, payload: object) -> CdekHttpResponse:
    return CdekHttpResponse(
        status=status,
        body=json.dumps(payload, ensure_ascii=False).encode(),
    )


def test_cdek_transport_caches_oauth_and_sends_exact_request_bytes() -> None:
    async def scenario() -> None:
        session = FakeAiohttpSession(
            [
                FakeAiohttpResponse(
                    200,
                    json.dumps({"access_token": "cdek-token", "expires_in": 60}).encode(),
                ),
                FakeAiohttpResponse(202, b'{"entity":{"uuid":"first"}}'),
                FakeAiohttpResponse(202, b'{"entity":{"uuid":"second"}}'),
            ]
        )
        settings = Settings(
            _env_file=None,
            cdek_client_id="client-id",
            cdek_client_secret="client-secret",
        )
        transport = AiohttpCdekTransport(settings, session=session)  # type: ignore[arg-type]
        first_body = b'{"number":"GB-1"}'
        second_body = b'{"number":"GB-2"}'

        assert (await transport.create_order(first_body)).status == 202
        assert (await transport.create_order(second_body)).status == 202

        assert len(session.posts) == 3
        token_url, token_data, token_headers, token_redirects = session.posts[0]
        assert token_url == "https://api.cdek.ru/v2/oauth/token"
        assert token_data == {
            "grant_type": "client_credentials",
            "client_id": "client-id",
            "client_secret": "client-secret",
        }
        assert token_headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert not token_redirects
        assert [request[1] for request in session.posts[1:]] == [first_body, second_body]
        assert [request[2]["Authorization"] for request in session.posts[1:]] == [
            "Bearer cdek-token",
            "Bearer cdek-token",
        ]

    asyncio.run(scenario())


def test_cdek_transport_sends_exact_quote_bytes_without_redirects() -> None:
    async def scenario() -> None:
        session = FakeAiohttpSession(
            [
                FakeAiohttpResponse(
                    200,
                    json.dumps({"access_token": "cdek-token", "expires_in": 60}).encode(),
                ),
                FakeAiohttpResponse(200, b'{"delivery_sum":450}'),
            ]
        )
        settings = Settings(
            _env_file=None,
            cdek_client_id="client-id",
            cdek_client_secret="client-secret",
        )
        transport = AiohttpCdekTransport(settings, session=session)  # type: ignore[arg-type]
        body = b'{"tariff_code":136}'

        assert (await transport.calculate_tariff(body)).status == 200

        url, sent_body, headers, redirects = session.posts[1]
        assert url == "https://api.cdek.ru/v2/calculator/tariff"
        assert sent_body == body
        assert headers == {
            "Authorization": "Bearer cdek-token",
            "Content-Type": "application/json",
        }
        assert not redirects

    asyncio.run(scenario())


def test_cdek_provider_parses_and_validates_tariff_quotes() -> None:
    async def scenario() -> None:
        transport = FakeCdekTransport(
            quote_response=_response(
                200,
                {"delivery_sum": "450.125", "period_min": 2, "period_max": 4},
            )
        )
        provider = CdekProviderClient(transport)
        body = b'{"tariff_code":136}'

        quote = await provider.calculate_tariff(body)

        assert transport.quoted_bodies == [body]
        assert quote.delivery_sum == Decimal("450.13")
        assert quote.period_min == 2
        assert quote.period_max == 4

        for payload in (
            {"delivery_sum": True},
            {"delivery_sum": "NaN"},
            {"delivery_sum": -1},
            {"delivery_sum": 100, "period_min": 5, "period_max": 2},
        ):
            invalid = CdekProviderClient(FakeCdekTransport(quote_response=_response(200, payload)))
            with pytest.raises(CdekProviderError, match="invalid_quote_response") as error:
                await invalid.calculate_tariff(b"{}")
            assert error.value.retryable
            assert not error.value.outcome_unknown

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status", "code", "retryable", "rejected"),
    [
        (401, "authentication", False, False),
        (422, "request_rejected", False, True),
        (429, "rate_limited", True, False),
        (503, "unavailable", True, False),
    ],
)
def test_cdek_quote_provider_classifies_http_failures(
    status: int,
    code: str,
    retryable: bool,
    rejected: bool,
) -> None:
    async def scenario() -> None:
        provider = CdekProviderClient(
            FakeCdekTransport(quote_response=CdekHttpResponse(status=status, body=b"{}"))
        )
        with pytest.raises(CdekProviderError, match=code) as error:
            await provider.calculate_tariff(b"{}")
        assert error.value.retryable is retryable
        assert error.value.rejected is rejected
        assert not error.value.outcome_unknown

    asyncio.run(scenario())


def test_cdek_provider_parses_create_and_get_snapshots() -> None:
    async def scenario() -> None:
        transport = FakeCdekTransport(
            create_response=_response(
                202,
                {
                    "entity": {"uuid": "cdek-order-260", "number": "GB-0000000260"},
                    "requests": [{"state": "ACCEPTED", "errors": [], "warnings": []}],
                },
            ),
            get_response=_response(
                200,
                {
                    "entity": {
                        "uuid": "cdek-order-260",
                        "number": "GB-0000000260",
                        "cdek_number": 1106153417,
                        "statuses": [
                            {"code": "ACCEPTED", "name": "Принят"},
                            {"code": "CREATED", "name": "Создан"},
                        ],
                    }
                },
            ),
        )
        provider = CdekProviderClient(transport)
        body = b'{"number":"GB-0000000260"}'

        created = await provider.create_order(body)
        observed = await provider.get_order("cdek-order-260")

        assert transport.created_bodies == [body]
        assert created.provider_uuid == "cdek-order-260"
        assert created.client_order_number == "GB-0000000260"
        assert observed.provider_uuid == "cdek-order-260"
        assert observed.cdek_number == "1106153417"
        assert observed.status_code == "CREATED"
        assert observed.status_name == "Создан"

    asyncio.run(scenario())


def test_cdek_provider_separates_rejection_from_ambiguous_outcomes() -> None:
    async def scenario() -> None:
        rejected = CdekProviderClient(
            FakeCdekTransport(
                create_response=_response(
                    202,
                    {
                        "requests": [
                            {"state": "INVALID", "errors": [{"code": "v2_order_invalid"}]}
                        ],
                    },
                )
            )
        )
        with pytest.raises(CdekProviderError) as rejected_error:
            await rejected.create_order(b"{}")
        assert rejected_error.value.code == "request_rejected"
        assert rejected_error.value.rejected
        assert not rejected_error.value.outcome_unknown
        assert rejected_error.value.provider_uuid is None

        invalid = CdekProviderClient(
            FakeCdekTransport(create_response=CdekHttpResponse(status=202, body=b"not-json"))
        )
        with pytest.raises(CdekProviderError) as invalid_error:
            await invalid.create_order(b"{}")
        assert invalid_error.value.code == "invalid_response"
        assert invalid_error.value.retryable
        assert invalid_error.value.outcome_unknown

        invalid_uuid = CdekProviderClient(
            FakeCdekTransport(
                create_response=_response(
                    202,
                    {"entity": {"uuid": "unsafe/provider/uuid"}},
                )
            )
        )
        with pytest.raises(CdekProviderError) as invalid_uuid_error:
            await invalid_uuid.create_order(b"{}")
        assert invalid_uuid_error.value.code == "invalid_response"
        assert invalid_uuid_error.value.outcome_unknown

        unavailable = CdekProviderClient(
            FakeCdekTransport(create_response=CdekHttpResponse(status=503, body=b""))
        )
        with pytest.raises(CdekProviderError) as unavailable_error:
            await unavailable.create_order(b"{}")
        assert unavailable_error.value.code == "unavailable"
        assert unavailable_error.value.outcome_unknown

    asyncio.run(scenario())


def test_cdek_provider_rejects_mismatched_get_identity() -> None:
    async def scenario() -> None:
        provider = CdekProviderClient(
            FakeCdekTransport(
                get_response=_response(
                    200,
                    {"entity": {"uuid": "different-cdek-order"}},
                )
            )
        )
        with pytest.raises(CdekProviderError, match="invalid_response") as error:
            await provider.get_order("expected-cdek-order")
        assert error.value.retryable

    asyncio.run(scenario())
