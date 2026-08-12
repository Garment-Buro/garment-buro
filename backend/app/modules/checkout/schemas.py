from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CheckoutResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: int = Field(gt=0)
    order_replayed: bool
    order_status: str = Field(min_length=1, max_length=32)
    order_payment_status: str = Field(min_length=1, max_length=32)
    total_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB"]
    payment_attempt_id: int = Field(gt=0)
    payment_attempt_number: int = Field(gt=0)
    payment_attempt_status: str = Field(min_length=1, max_length=32)
    payment_replayed: bool
    payment_url: str | None = Field(default=None, max_length=4096)


class CheckoutResponse(BaseModel):
    """Compatibility response consumed by the current web and PWA checkout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: int = Field(gt=0)
    payment_url: str | None = Field(default=None, max_length=4096)
