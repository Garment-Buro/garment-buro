from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ProfileSlug = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$", min_length=3, max_length=64)
]
PublicName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120, pattern=r"^[^\x00]*$"),
]
PublicBio = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000, pattern=r"^[^\x00]*$")
]


class PublicProfileWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: ProfileSlug
    display_name: PublicName
    bio: PublicBio = ""
    is_published: bool = Field(strict=True)
    version: int = Field(strict=True, ge=0, le=2_147_483_646)


class PublicProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    display_name: str
    bio: str
    avatar_id: int | None = Field(default=None, validation_alias="avatar_media_id")


class OwnPublicProfileResponse(PublicProfileResponse):
    is_published: bool
    version: int


class PeopleQuery(BaseModel):
    query: str = Field(default="", max_length=200, pattern=r"^[^\x00]*$")
    sort: Literal["newest", "name"] = "newest"
    limit: int = Field(default=24, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)


class PeoplePageResponse(BaseModel):
    items: list[PublicProfileResponse]
    next_cursor: str | None
