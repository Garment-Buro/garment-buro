from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

InboxKind = Literal["support", "production_problem"]
InboxStatus = Literal["new", "in_progress", "resolved", "closed"]
InboxPriority = Literal["low", "normal", "high", "critical"]


class AdminInboxRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: InboxKind
    status: InboxStatus
    priority: InboxPriority
    subject: str
    message: str
    reporter_user_id: int | None
    reporter_name: str | None
    reporter_email: str | None
    reporter_phone: str | None
    order_id: int | None
    project_id: int | None
    production_unit_id: int | None
    station: str | None
    assigned_to_user_id: int | None
    admin_note: str | None
    version: int
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminInboxPage(BaseModel):
    items: list[AdminInboxRead]
    next_offset: int | None


class SupportRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(default="Обращение пользователя", min_length=1, max_length=255)
    message: str = Field(min_length=3, max_length=5000)
    order_id: int | None = Field(default=None, gt=0)


class SupportRequestCreated(BaseModel):
    id: int
    status: InboxStatus
    created_at: datetime


class AdminInboxUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_version: int = Field(gt=0)
    status: InboxStatus
    priority: InboxPriority
    assigned_to_user_id: int | None = Field(default=None, gt=0)
    admin_note: str | None = Field(default=None, max_length=5000)

    @field_validator("admin_note", mode="after")
    @classmethod
    def empty_note_is_none(cls, value: str | None) -> str | None:
        return value or None
