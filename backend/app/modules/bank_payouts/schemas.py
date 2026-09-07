from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BankPayoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Accounting chooses contractual basis and VAT wording; never infer these from a profile.
    payment_purpose: str = Field(min_length=10, max_length=160)

    @field_validator("payment_purpose")
    @classmethod
    def normalize_purpose(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 10 or any(ord(char) < 32 for char in normalized):
            raise ValueError("Payment purpose is invalid")
        return normalized


class BankPayoutSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payout_id: int
    provider: Literal["tochka"]
    environment: Literal["sandbox", "production"]
    state: Literal[
        "submitting", "unknown", "awaiting_signature", "processing", "paid", "rejected", "canceled"
    ]
    provider_status: str | None
    last_checked_at: datetime | None
    created_at: datetime


class BankPayoutAdminResponse(BankPayoutSummary):
    request_id: str | None
    signing_url: str | None
    last_error: str | None
