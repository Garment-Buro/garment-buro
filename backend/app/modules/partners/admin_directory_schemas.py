from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminLandingQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=100)
    status: Literal["draft", "published", "archived"] | None = None
    limit: int = Field(default=24, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str) -> str:
        return value.strip()


class AdminLandingCard(BaseModel):
    id: int
    version: int
    title: str
    slug: str
    image_url: str | None
    status: Literal["draft", "published", "archived"]
    partner_id: int
    partner_name: str
    product_count: int


class AdminLandingPage(BaseModel):
    items: list[AdminLandingCard]
    next_cursor: str | None
