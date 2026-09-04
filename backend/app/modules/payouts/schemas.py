from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9._~:-]{1,64}$")


class PayoutAmount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB"] = "RUB"


class PayoutTokenDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["payout_token"]
    token: SecretStr

    @model_validator(mode="after")
    def validate_token(self) -> PayoutTokenDestination:
        value = self.token.get_secret_value()
        if not 1 <= len(value) <= 4096:
            raise ValueError("Payout token length is invalid")
        return self


class SavedPaymentMethodDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["payment_method"]
    payment_method_id: str = Field(min_length=1, max_length=255)

    @field_validator("payment_method_id")
    @classmethod
    def normalize_payment_method_id(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{1,255}", normalized):
            raise ValueError("Saved payment method ID is invalid")
        return normalized


class BankCardPayoutDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bank_card"]
    card_number: SecretStr

    @model_validator(mode="after")
    def validate_card_number(self) -> BankCardPayoutDestination:
        value = self.card_number.get_secret_value()
        if not re.fullmatch(r"\d{16,19}", value):
            raise ValueError("Payout card number must contain 16-19 digits")
        return self


class YooMoneyPayoutDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["yoo_money"]
    account_number: str

    @field_validator("account_number")
    @classmethod
    def validate_account_number(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"\d{11,33}", normalized):
            raise ValueError("YooMoney account number must contain 11-33 digits")
        return normalized


class SbpPayoutDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["sbp"]
    phone: str
    bank_id: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = value.strip().removeprefix("+")
        if not re.fullmatch(r"\d{4,15}", normalized):
            raise ValueError("SBP phone must use E.164 digits")
        return normalized

    @field_validator("bank_id")
    @classmethod
    def validate_bank_id(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9]{12}", normalized):
            raise ValueError("SBP bank ID must contain 12 letters or digits")
        return normalized


PayoutDestination = Annotated[
    PayoutTokenDestination
    | SavedPaymentMethodDestination
    | BankCardPayoutDestination
    | YooMoneyPayoutDestination
    | SbpPayoutDestination,
    Field(discriminator="type"),
]


class PayoutCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: PayoutAmount
    destination: PayoutDestination
    description: str = Field(min_length=1, max_length=128)
    reference: str | None = Field(default=None, max_length=64)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Payout description must not be blank")
        return normalized

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not REFERENCE_PATTERN.fullmatch(normalized):
            raise ValueError("Payout reference contains unsupported characters")
        return normalized

    def canonical_provider_bytes(self, *, internal_payout_id: int) -> bytes:
        destination = self.destination
        payload: dict[str, object] = {
            "amount": self.amount.model_dump(mode="json"),
            "description": self.description,
            "metadata": {"internal_payout_id": str(internal_payout_id)},
        }
        if self.reference is not None:
            payload["metadata"]["reference"] = self.reference  # type: ignore[index]
        if isinstance(destination, PayoutTokenDestination):
            payload["payout_token"] = destination.token.get_secret_value()
        elif isinstance(destination, SavedPaymentMethodDestination):
            payload["payment_method_id"] = destination.payment_method_id
        elif isinstance(destination, BankCardPayoutDestination):
            payload["payout_destination_data"] = {
                "type": "bank_card",
                "card": {"number": destination.card_number.get_secret_value()},
            }
        elif isinstance(destination, YooMoneyPayoutDestination):
            payload["payout_destination_data"] = {
                "type": "yoo_money",
                "account_number": destination.account_number,
            }
        else:
            payload["payout_destination_data"] = {
                "type": "sbp",
                "phone": destination.phone,
                "bank_id": destination.bank_id,
            }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


class YooKassaPayoutResponseAmount(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB"]


class YooKassaPayoutResponseDestination(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["bank_card", "yoo_money", "sbp"]


class YooKassaPayoutResponseMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    internal_payout_id: int = Field(gt=0)
    reference: str | None = None


class YooKassaPayoutCancellation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    party: Literal["yoo_money", "payout_network"]
    reason: str = Field(min_length=1, max_length=64)


class YooKassaPayoutResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=36, max_length=50)
    amount: YooKassaPayoutResponseAmount
    status: Literal["pending", "succeeded", "canceled"]
    payout_destination: YooKassaPayoutResponseDestination
    description: str = Field(min_length=1, max_length=128)
    created_at: datetime
    succeeded_at: datetime | None = None
    cancellation_details: YooKassaPayoutCancellation | None = None
    metadata: YooKassaPayoutResponseMetadata
    test: bool

    @field_validator("created_at", "succeeded_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Payout timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_status_evidence(self) -> YooKassaPayoutResponse:
        if self.status == "succeeded" and self.succeeded_at is None:
            raise ValueError("Succeeded payout must include succeeded_at")
        if self.status != "succeeded" and self.succeeded_at is not None:
            raise ValueError("Only succeeded payout may include succeeded_at")
        if self.status == "canceled" and self.cancellation_details is None:
            raise ValueError("Canceled payout must include cancellation details")
        if self.status != "canceled" and self.cancellation_details is not None:
            raise ValueError("Cancellation details require canceled status")
        return self


class PayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    id: int = Field(gt=0)
    amount: Decimal
    currency: Literal["RUB"]
    description: str
    reference: str | None
    requested_destination_type: str
    provider_destination_type: str | None
    status: str
    provider_payout_id: str | None
    provider_created_at: datetime | None
    succeeded_at: datetime | None
    cancellation_party: str | None
    cancellation_reason: str | None
    test: bool | None
    replayed: bool = False
