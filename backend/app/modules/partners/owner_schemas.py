"""Bounded owner editor reads; public directory schemas remain separate."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OwnerLandingQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=24, ge=1, le=24)
    cursor: str | None = Field(default=None, min_length=1, max_length=512)


class OwnerLandingPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(strict=True, ge=1, le=1)
    partner_id: int = Field(strict=True, gt=0, le=2_147_483_647)
    id: int = Field(strict=True, gt=0, le=2_147_483_647)


class OwnerLandingCard(BaseModel):
    id: int
    version: int
    slug: str
    title: str
    image_url: str | None
    status: Literal["draft", "published", "archived"]
    product_count: int


class OwnerLandingPage(BaseModel):
    items: list[OwnerLandingCard]
    next_cursor: str | None
