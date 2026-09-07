import asyncio

import aiohttp
import pytest

from app.core.config import Settings
from app.integrations.tochka.transport import MAX_RESPONSE_BYTES, TochkaTransport
from app.modules.bank_payouts.contracts import BankProviderError


class Response:
    status = 200

    def __init__(self, chunks):
        self.chunks = chunks
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        for chunk in self.chunks:
            yield chunk


class Session:
    def __init__(self, chunks=(), error=None):
        self.calls = []
        self.chunks, self.error = chunks, error

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.error:
            raise self.error
        return Response(self.chunks)


@pytest.mark.parametrize(
    "environment,token", [("sandbox", "sandbox.jwt.token"), ("production", "test-only-token")]
)
def test_transport_bearer_auth_json_and_redirect_protection(environment, token):
    transport = TochkaTransport(
        Settings(_env_file=None, tochka_environment=environment, tochka_api_token="test-only-token")
    )
    session = Session(chunks=[b'{"Data":', b"{}}"])
    transport.session = session
    response = asyncio.run(transport.request("POST", "/payment/v1.0/for-sign", b"request"))
    assert response.body == b'{"Data":{}}'
    assert len(session.calls) == 1
    method, url, kwargs = session.calls[0]
    assert method == "POST" and url.startswith("https://enter.tochka.com/")
    assert kwargs == {
        "data": b"request",
        "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        "allow_redirects": False,
    }


@pytest.mark.parametrize(
    "error", [asyncio.TimeoutError(), aiohttp.ClientConnectionError("private details")]
)
def test_network_failure_never_retries_post_or_exposes_raw_error(error):
    transport = TochkaTransport(Settings(_env_file=None))
    transport.session = Session(error=error)
    with pytest.raises(BankProviderError, match="^network_error$") as caught:
        asyncio.run(transport.request("POST", "/payment/v1.0/for-sign", b"{}"))
    assert caught.value.outcome_unknown
    assert len(transport.session.calls) == 1


def test_response_size_is_bounded():
    transport = TochkaTransport(Settings(_env_file=None))
    transport.session = Session(chunks=[b"x" * MAX_RESPONSE_BYTES, b"x"])
    with pytest.raises(BankProviderError, match="response_too_large"):
        asyncio.run(transport.request("POST", "/payment/v1.0/for-sign", b"{}"))


def test_client_lifecycle_is_idempotent():
    async def scenario():
        transport = TochkaTransport(Settings(_env_file=None))
        await transport.startup()
        session = transport.session
        try:
            assert session.trust_env is False
            assert session.timeout.total == 15
            await transport.startup()
            assert transport.session is session
        finally:
            await transport.shutdown()
            await transport.shutdown()
        assert session.closed and transport.session is None

    asyncio.run(scenario())
