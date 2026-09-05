from pydantic import BaseModel, Field, field_validator

from app.modules.delivery.validation import normalize_cdek_phone
from app.modules.identity.exceptions import InvalidEmailError
from app.modules.identity.security import normalize_email


class CheckoutContact(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=7, max_length=64)
    email: str = Field(min_length=3, max_length=320)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Укажите полное имя")
        return value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str) -> str:
        return normalize_cdek_phone(value)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        try:
            return normalize_email(value)[1]
        except InvalidEmailError as error:
            raise ValueError("Укажите корректную почту") from error
