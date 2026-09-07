from __future__ import annotations

import json
import re
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from app.integrations.tochka.transport import BankHttpResponse
from app.modules.bank_payouts.contracts import BankDraft, BankPaymentStatus, BankProviderError

REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
BANK_STATUSES = {"WaitingForCreate", "Created", "Paid", "Canceled", "Rejected"}


class BankTransport(Protocol):
    async def request(
        self, method: str, path: str, body: bytes | None = None
    ) -> BankHttpResponse: ...


class TochkaPayoutProvider:
    def __init__(self, transport: BankTransport) -> None:
        self.transport = transport

    async def create_draft(self, request_body: bytes) -> BankDraft:
        response = await self.transport.request("POST", "/payment/v1.0/for-sign", request_body)
        data = self._data(response)
        request_id = self._request_id(data.get("requestId"))
        signing_url = data.get("redirectURL")
        if not isinstance(signing_url, str) or len(signing_url) > 4096:
            raise BankProviderError("invalid_signing_url")
        try:
            parsed = urlsplit(signing_url)
            valid = self._bank_url(parsed)
            if parsed.path == "/api/v1/auth/oauth/start":
                query = parse_qs(parsed.query, strict_parsing=True)
                valid = (
                    valid
                    and parsed.hostname == "i.tochka.com"
                    and set(query) == {"path"}
                    and len(query["path"]) == 1
                )
                target = urlsplit(query["path"][0]) if valid else parsed
            else:
                target = parsed
            valid = (
                valid
                and self._bank_url(target)
                and target.path == f"/bank/m/payment-preview/{request_id}"
            )
        except ValueError:
            valid = False
        if not valid:
            raise BankProviderError("invalid_signing_url")
        return BankDraft(request_id=request_id, signing_url=signing_url)

    @staticmethod
    def _bank_url(parsed) -> bool:
        return (
            parsed.scheme == "https"
            and parsed.hostname in {"i.tochka.com", "enter.tochka.com"}
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and "\\" not in parsed.netloc
        )

    async def get_status(self, request_id: str) -> BankPaymentStatus:
        self._request_id(request_id)
        response = await self.transport.request("GET", f"/payment/v1.0/status/{request_id}")
        data = self._data(response)
        if self._request_id(data.get("requestId")) != request_id:
            raise BankProviderError("request_id_mismatch")
        status = data.get("status")
        if not isinstance(status, str) or status not in BANK_STATUSES:
            raise BankProviderError("unknown_bank_status")
        return BankPaymentStatus(request_id=request_id, status=status)

    @staticmethod
    def _request_id(value: object) -> str:
        if not isinstance(value, str) or not REQUEST_ID.fullmatch(value):
            raise BankProviderError("invalid_request_id")
        return value

    @staticmethod
    def _data(response: BankHttpResponse) -> dict:
        if response.status != 200:
            raise BankProviderError(
                f"http_{response.status}", outcome_unknown=response.status not in {400, 401, 403}
            )
        try:
            payload = json.loads(response.body)
        except (ValueError, UnicodeError) as error:
            raise BankProviderError("invalid_json") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("Data"), dict):
            raise BankProviderError("invalid_response")
        return payload["Data"]
