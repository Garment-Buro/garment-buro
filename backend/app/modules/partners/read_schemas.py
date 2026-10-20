"""Bounded private profile directory and owner payout history."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.modules.partners.schemas import PartnerPayoutResponse, PartnerProfileResponse


class AdminPartnerQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=100)
    status: Literal["invited", "active", "suspended"] | None = None
    selectable: bool = False
    limit: int = Field(default=24, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str) -> str:
        return value.strip()


class PartnerPayoutQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=24, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)


class AdminPartnerPage(BaseModel):
    items: list[PartnerProfileResponse]
    next_cursor: str | None


class PartnerPayoutPage(BaseModel):
    items: list[PartnerPayoutResponse]
    next_cursor: str | None


class AdminPartnerPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(ge=1, le=1)
    kind: Literal["profiles"]
    id: int = Field(gt=0, le=2_147_483_647)
    filters: str = Field(pattern=r"^[a-f0-9]{64}$")


class PartnerPayoutPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(ge=1, le=1)
    kind: Literal["payouts"]
    id: int = Field(gt=0, le=2_147_483_647)
    partner_id: int = Field(gt=0, le=2_147_483_647)
    created_at: AwareDatetime
