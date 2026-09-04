from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaymentOperationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    operation_id: int = Field(gt=0)
    payment_attempt_id: int = Field(gt=0)
    order_id: int = Field(gt=0)
    operation: Literal["capture", "cancel"]
    operation_status: Literal["prepared", "unknown", "succeeded", "failed"]
    payment_status: Literal["pending", "waiting_for_capture", "succeeded", "canceled"]
    provider_payment_id: str = Field(min_length=1, max_length=255)
    capture_expires_at: datetime | None = None
    replayed: bool


class OrderPaymentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    payment_id: int = Field(gt=0)
    payment_attempt_id: int = Field(gt=0)
    order_id: int = Field(gt=0)
    capture_mode: Literal["automatic", "manual"]
    status: str
    provider_payment_id: str | None
    confirmation_url: str | None
    capture_expires_at: datetime | None
