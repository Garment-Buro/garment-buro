from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthEmailRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=3, max_length=320)


class AuthVerifyRequest(AuthEmailRequest):
    code: str = Field(pattern=r"^\d{4}$")


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    gender: str | None = Field(default=None, max_length=32)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=64)
    height: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    weight: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    email: str | None = Field(default=None, max_length=320)

    @field_validator(
        "first_name",
        "last_name",
        "gender",
        "birth_date",
        "phone",
        "height",
        "weight",
        "email",
        mode="before",
    )
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value


class AuthUserResponse(BaseModel):
    id: int
    email: str | None
    phone: str | None
    first_name: str | None
    last_name: str | None
    username: str | None
    gender: str | None
    birth_date: date | None
    height: float | None
    weight: float | None
    created_at: datetime


class AuthSessionResponse(BaseModel):
    token: str
    user: AuthUserResponse


class AuthAccessResponse(BaseModel):
    roles: list[str]
    permissions: list[str]


class EmailCodeRequestResponse(BaseModel):
    status: Literal["sent"] = "sent"


class DeletedResponse(BaseModel):
    status: Literal["deleted"] = "deleted"


class LoggedOutResponse(BaseModel):
    status: Literal["logged_out"] = "logged_out"
