from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.production.inbox_schemas import SupportRequestCreate


class TicketReply(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=5000)
    visibility: Literal["public", "internal"] = "public"


class AdminTicketCreate(SupportRequestCreate):
    customer_user_id: int | None = Field(default=None, gt=0)


class TicketRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(gt=0)
    target: str = Field(min_length=1, max_length=24)
    comment: str = Field(min_length=3, max_length=1000)
