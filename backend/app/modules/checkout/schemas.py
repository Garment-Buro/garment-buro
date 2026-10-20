from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.checkout.contact import CheckoutContact
from app.modules.orders.schemas import MAX_ORDER_ITEMS, OrderCreationCommand, OrderLineCreate


class CheckoutCommand(BaseModel):
    """Public purchase boundary; contacts are mapped explicitly into snapshots."""

    model_config = ConfigDict(extra="forbid")

    buyer: CheckoutContact
    recipient: CheckoutContact
    delivery_city: str = Field(min_length=1, max_length=255)
    delivery_method: str = Field(min_length=1, max_length=64)
    delivery_address: str = Field(min_length=1, max_length=4096)
    cdek_point_code: str | None = Field(default=None, max_length=64)
    payment_method: str = Field(min_length=1, max_length=64)
    payment_capture_mode: Literal["automatic", "manual"] = "automatic"
    items: list[OrderLineCreate] = Field(min_length=1, max_length=MAX_ORDER_ITEMS)
    claimed_total_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    delivery_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    delivery_quote_token: str = Field(min_length=1, max_length=4096)
    currency: Literal["RUB"] = "RUB"

    def to_order_command(self) -> OrderCreationCommand:
        return OrderCreationCommand.model_validate(
            {
                **self.model_dump(exclude={"buyer", "recipient"}),
                "email": self.buyer.email,
                "buyer_name": self.buyer.name,
                "buyer_phone": self.buyer.phone,
                "phone": self.recipient.phone,
                # Preserve the supplied full name without guessing its parts.
                "first_name": self.recipient.name,
                "recipient_email": self.recipient.email,
            }
        )


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
