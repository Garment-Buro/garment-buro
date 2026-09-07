from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

BankStatus = Literal["WaitingForCreate", "Created", "Paid", "Canceled", "Rejected"]


@dataclass(frozen=True)
class BankDraft:
    request_id: str
    signing_url: str


@dataclass(frozen=True)
class BankPaymentStatus:
    request_id: str
    status: BankStatus


class BankProviderError(RuntimeError):
    def __init__(self, code: str, *, outcome_unknown: bool = True) -> None:
        super().__init__(code)
        self.code = code
        self.outcome_unknown = outcome_unknown


class BankPayoutProvider(Protocol):
    async def create_draft(self, request_body: bytes) -> BankDraft: ...

    async def get_status(self, request_id: str) -> BankPaymentStatus: ...
