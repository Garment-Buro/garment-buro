import asyncio
import json
import ssl
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.integrations.tochka.mapping import bank_request
from app.integrations.tochka.provider import TochkaPayoutProvider
from app.integrations.tochka.transport import BankHttpResponse, TochkaTransport, bank_ssl_context
from app.modules.bank_payouts.contracts import BankProviderError
from app.modules.partners.schemas import PartnerRequisitesRequest

REQUEST_ID = "openapi-test-123"
SIGNING_URL = f"https://i.tochka.com/bank/m/payment-preview/{REQUEST_ID}?customerCode=1234567ab"
REQUISITES = dict(
    entity_type="sole_proprietor",
    recipient_name="ИП Тестовый Получатель",
    tax_id="123456789012",
    bank_name="Тестовый банк",
    bic="044525225",
    correspondent_account="30101810400000000225",
    settlement_account="40802810900000000001",
)


class Transport:
    def __init__(self, data, status=200):
        self.response = BankHttpResponse(status, json.dumps(data).encode())
        self.calls = []

    async def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        return self.response


def test_create_draft_exact_contract_and_auth_redirect():
    async def scenario():
        url = f"https://i.tochka.com/api/v1/auth/oauth/start?path=https%3A//enter.tochka.com/bank/m/payment-preview/{REQUEST_ID}%3FcustomerCode%3D1234567ab"
        transport = Transport({"Data": {"requestId": REQUEST_ID, "redirectURL": url}})
        draft = await TochkaPayoutProvider(transport).create_draft(b'{"Data":{}}')
        assert draft.request_id == REQUEST_ID and draft.signing_url == url
        assert transport.calls == [("POST", "/payment/v1.0/for-sign", b'{"Data":{}}')]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "url",
    [
        "http://i.tochka.com/bank/m/payment-preview/openapi-test-123",
        "https://evil.test/",
        "https://i.tochka.com.evil.test/",
        "https://user@i.tochka.com/",
        "https://i.tochka.com/api/v1/auth/oauth/start?path=https://evil.test/",
        "https://i.tochka.com/api/v1/auth/oauth/start?path=https://enter.tochka.com/other",
        "https://i.tochka.com:invalid/",
        "https://i.tochka.com/bank/m/payment-preview/other",
    ],
)
def test_untrusted_signing_urls_fail_closed(url):
    transport = Transport({"Data": {"requestId": REQUEST_ID, "redirectURL": url}})
    with pytest.raises(BankProviderError, match="invalid_signing_url"):
        asyncio.run(TochkaPayoutProvider(transport).create_draft(b"{}"))


@pytest.mark.parametrize("status", ["WaitingForCreate", "Created", "Paid", "Canceled", "Rejected"])
def test_status_exact_contract(status):
    transport = Transport({"Data": {"requestId": REQUEST_ID, "status": status}})
    result = asyncio.run(TochkaPayoutProvider(transport).get_status(REQUEST_ID))
    assert result.status == status
    assert transport.calls == [("GET", f"/payment/v1.0/status/{REQUEST_ID}", None)]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"Data": []},
        {"Data": {"requestId": "other", "status": "Paid"}},
        {"Data": {"requestId": REQUEST_ID, "status": "NewStatus"}},
    ],
)
def test_invalid_status_evidence_is_not_success(data):
    with pytest.raises(BankProviderError):
        asyncio.run(TochkaPayoutProvider(Transport(data)).get_status(REQUEST_ID))


@pytest.mark.parametrize(
    "status,unknown",
    [(400, False), (401, False), (403, False), (429, True), (500, True), (302, True)],
)
def test_http_errors_are_sanitized_and_ambiguity_preserved(status, unknown):
    transport = Transport({"error": "sensitive bank details"}, status)
    with pytest.raises(BankProviderError) as caught:
        asyncio.run(TochkaPayoutProvider(transport).create_draft(b"{}"))
    assert caught.value.outcome_unknown is unknown
    assert str(caught.value) == f"http_{status}"
    assert len(transport.calls) == 1


def test_tls_verification_and_environment_isolation():
    context = bank_ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    sandbox = TochkaTransport(Settings(_env_file=None))
    assert sandbox.base_url == "https://enter.tochka.com/sandbox/v2"
    with pytest.raises(BankProviderError, match="transport_not_started"):
        asyncio.run(sandbox.request("POST", "/payment/v1.0/for-sign", b"{}"))


def test_mapping_uses_rubles_and_moscow_date():
    payload, body = bank_request(
        settings=Settings(_env_file=None),
        payout_id=17,
        amount=Decimal("700.33"),
        requisites=PartnerRequisitesRequest(**REQUISITES),
        purpose="Вознаграждение по договору 1. Без НДС.",
        now=datetime(2026, 9, 8, 23, tzinfo=timezone.utc),
    )
    data = payload["Data"]
    assert json.loads(body) == payload
    assert data["paymentAmount"] == 700.33
    assert data["paymentDate"] == "2026-09-09"
    assert data["counterpartyKPP"] == "0"
    assert data["accountCode"] == "12345810901234567890"
    assert data["paymentPurpose"].endswith("[GB-PAYOUT-17]")


@pytest.mark.parametrize("amount", ["0", "-1", "1.001", "NaN", "Infinity", "10000000000"])
def test_mapping_rejects_invalid_amount(amount):
    with pytest.raises(ValueError):
        bank_request(
            settings=Settings(_env_file=None),
            payout_id=1,
            amount=Decimal(amount),
            requisites=PartnerRequisitesRequest(**REQUISITES),
            purpose="Test purpose",
            now=datetime.now(timezone.utc),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"entity_type": "self_employed"},
        {"settlement_account": "40817810900000000001"},
        {"settlement_account": "40802840900000000001"},
    ],
)
def test_mapping_restricts_payouts_to_rub_ip_accounts(changes):
    with pytest.raises(ValueError):
        bank_request(
            settings=Settings(_env_file=None),
            payout_id=1,
            amount=Decimal("1.00"),
            requisites=PartnerRequisitesRequest(**(REQUISITES | changes)),
            purpose="Test purpose",
            now=datetime.now(timezone.utc),
        )
