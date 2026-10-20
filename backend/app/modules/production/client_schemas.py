from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClientHistoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=3, max_length=512)
    limit: int = Field(default=24, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=2048)

    @field_validator("key")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Invalid client key")
        return value


class ClientOrderSummary(BaseModel):
    id: int
    created_at: datetime
    total: str
    status: str
    payment_status: str
    workflow_state: str | None
    delivery_city: str | None
    delivery_method: str | None
    payment_method: str | None


class ClientTicketSummary(BaseModel):
    id: int
    subject: str
    status: str
    priority: str
    order_id: int | None
    created_at: datetime
    updated_at: datetime


Item = TypeVar("Item", ClientOrderSummary, ClientTicketSummary)


class ClientHistoryPage(BaseModel, Generic[Item]):
    items: list[Item]
    next_cursor: str | None
