from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class AuthEmailRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=3, max_length=320)


class AuthVerifyRequest(AuthEmailRequest):
    code: str = Field(pattern=r"^\d{4}$")


class AuthPhoneRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    phone: str = Field(min_length=8, max_length=64)


class AuthPhoneVerifyRequest(AuthPhoneRequest):
    code: str = Field(pattern=r"^\d{4}$")


class PasswordLoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identifier: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=10, max_length=128)


class SetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    new_password: SecretStr = Field(min_length=10, max_length=128)
    current_password: SecretStr | None = Field(default=None, min_length=10, max_length=128)


class TelegramLoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)
    auth_date: int = Field(gt=0)
    hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    photo_url: str | None = Field(default=None, max_length=2048)


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


class AuthMethodResponse(BaseModel):
    code: str
    kind: str
    enabled: bool
    reason: str | None


class AuthMethodsResponse(BaseModel):
    methods: list[AuthMethodResponse]


class EmailCodeRequestResponse(BaseModel):
    status: Literal["sent"] = "sent"


class DeletedResponse(BaseModel):
    status: Literal["deleted"] = "deleted"


class LoggedOutResponse(BaseModel):
    status: Literal["logged_out"] = "logged_out"


class PasswordUpdatedResponse(BaseModel):
    status: Literal["password_updated"] = "password_updated"
