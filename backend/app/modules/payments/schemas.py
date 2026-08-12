from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProviderPaymentStatus = Literal[
    "pending",
    "waiting_for_capture",
    "succeeded",
    "canceled",
]
ProviderPaymentEventType = Literal[
    "payment.waiting_for_capture",
    "payment.succeeded",
    "payment.canceled",
]
ReceiptPaymentMode = Literal[
    "full_prepayment",
    "partial_prepayment",
    "advance",
    "full_payment",
    "partial_payment",
    "credit",
    "credit_payment",
]
ReceiptPaymentSubject = Literal["commodity", "non_marked", "service"]


class YooKassaCreateAmount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB"] = "RUB"


class YooKassaCreatePaymentMethod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bank_card", "sbp"]


class YooKassaCreateConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["redirect"] = "redirect"
    return_url: str = Field(min_length=1, max_length=2048)

    @field_validator("return_url")
    @classmethod
    def validate_return_url(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Payment return URL must be an absolute safe HTTP(S) URL")
        return normalized


class YooKassaCreateMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int = Field(gt=0)


class YooKassaReceiptCustomer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or any(character.isspace() for character in normalized):
            raise ValueError("Receipt email is invalid")
        return normalized


class YooKassaReceiptItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=128)
    quantity: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    amount: YooKassaCreateAmount
    vat_code: int = Field(ge=1, le=12)
    payment_mode: ReceiptPaymentMode
    payment_subject: ReceiptPaymentSubject

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Receipt item description must not be blank")
        return normalized


class YooKassaReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer: YooKassaReceiptCustomer
    items: list[YooKassaReceiptItem] = Field(min_length=1, max_length=100)
    tax_system_code: int | None = Field(default=None, ge=1, le=6)


class YooKassaCreatePaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: YooKassaCreateAmount
    capture: Literal[True] = True
    payment_method_data: YooKassaCreatePaymentMethod
    confirmation: YooKassaCreateConfirmation
    description: str = Field(min_length=1, max_length=128)
    metadata: YooKassaCreateMetadata
    receipt: YooKassaReceipt

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Payment description must not be blank")
        return normalized

    @model_validator(mode="after")
    def receipt_total_matches_payment(self) -> YooKassaCreatePaymentRequest:
        receipt_total = sum(
            (item.amount.value * item.quantity for item in self.receipt.items),
            start=Decimal("0.00"),
        )
        if receipt_total != self.amount.value:
            raise ValueError("Receipt item total must match payment amount")
        return self

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


class ProviderPaymentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_payment_id: str = Field(min_length=1, max_length=255)
    status: ProviderPaymentStatus
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB"] = "RUB"
    metadata_order_id: int = Field(gt=0)
    payment_method: Literal["bank_card", "sbp"] | None = None
    paid: bool
    test: bool
    confirmation_url: str | None = Field(default=None, max_length=4096)
    provider_created_at: datetime | None = None
    captured_at: datetime | None = None
    cancellation_party: str | None = Field(default=None, max_length=64)
    cancellation_reason: str | None = Field(default=None, max_length=128)

    @field_validator("provider_payment_id")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Provider payment ID must not be blank")
        return normalized

    @field_validator("cancellation_party", "cancellation_reason")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("provider_created_at", "captured_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Provider timestamps must include a timezone")
        return value

    @field_validator("confirmation_url")
    @classmethod
    def validate_confirmation_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Payment confirmation URL must be an absolute HTTPS URL")
        return normalized

    @model_validator(mode="after")
    def validate_status_evidence(self) -> ProviderPaymentSnapshot:
        if self.status == "succeeded" and not self.paid:
            raise ValueError("Succeeded payment must be marked paid")
        if self.status == "waiting_for_capture" and not self.paid:
            raise ValueError("Payment waiting for capture must be marked paid")
        if self.status in {"pending", "canceled"} and self.paid:
            raise ValueError(f"{self.status} payment must not be marked paid")
        if self.status == "canceled" and (
            self.cancellation_party is None or self.cancellation_reason is None
        ):
            raise ValueError("Canceled payment must include cancellation evidence")
        if self.status != "canceled" and (
            self.cancellation_party is not None or self.cancellation_reason is not None
        ):
            raise ValueError("Cancellation evidence is valid only for canceled payments")
        return self


class ProviderPaymentEventObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: ProviderPaymentEventType
    payment: ProviderPaymentSnapshot

    @model_validator(mode="after")
    def validate_event_matches_status(self) -> ProviderPaymentEventObservation:
        expected_status = self.event_type.removeprefix("payment.")
        if self.payment.status != expected_status:
            raise ValueError("Payment event type does not match object status")
        return self


class YooKassaAmount(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB"]


class YooKassaMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    order_id: int = Field(gt=0)


class YooKassaPaymentMethod(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["bank_card", "sbp"]


class YooKassaConfirmation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    confirmation_url: str = Field(min_length=1, max_length=4096)


class YooKassaCancellationDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")

    party: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=128)


class YooKassaWebhookPayment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=255)
    status: ProviderPaymentStatus
    amount: YooKassaAmount
    metadata: YooKassaMetadata
    payment_method: YooKassaPaymentMethod | None = None
    paid: bool
    test: bool
    confirmation: YooKassaConfirmation | None = None
    created_at: datetime
    captured_at: datetime | None = None
    cancellation_details: YooKassaCancellationDetails | None = None

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Provider payment ID must not be blank")
        return normalized

    @field_validator("created_at", "captured_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Provider timestamps must include a timezone")
        return value

    def to_snapshot(self) -> ProviderPaymentSnapshot:
        cancellation = self.cancellation_details
        return ProviderPaymentSnapshot(
            provider_payment_id=self.id,
            status=self.status,
            amount=self.amount.value,
            currency=self.amount.currency,
            metadata_order_id=self.metadata.order_id,
            payment_method=(self.payment_method.type if self.payment_method is not None else None),
            paid=self.paid,
            test=self.test,
            confirmation_url=(
                self.confirmation.confirmation_url if self.confirmation is not None else None
            ),
            provider_created_at=self.created_at,
            captured_at=self.captured_at,
            cancellation_party=cancellation.party if cancellation is not None else None,
            cancellation_reason=cancellation.reason if cancellation is not None else None,
        )


class YooKassaWebhookEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["notification"]
    event: ProviderPaymentEventType
    object: YooKassaWebhookPayment

    def to_observation(self) -> ProviderPaymentEventObservation:
        return ProviderPaymentEventObservation(
            event_type=self.event,
            payment=self.object.to_snapshot(),
        )
