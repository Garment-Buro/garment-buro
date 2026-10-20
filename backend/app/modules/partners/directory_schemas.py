from typing import Literal

from pydantic import BaseModel, Field


class CommunityQuery(BaseModel):
    query: str = Field(default="", max_length=200, pattern=r"^[^\x00]*$")
    sort: Literal["newest", "name"] = "newest"
    limit: int = Field(default=24, ge=1, le=100)
    # A 255-character title may need six bytes per JSON escape, then base64 encoding.
    cursor: str | None = Field(default=None, max_length=4096)


class CommunityCardResponse(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    owner_name: str
    image_url: str | None


class CommunityPageResponse(BaseModel):
    items: list[CommunityCardResponse]
    next_cursor: str | None
