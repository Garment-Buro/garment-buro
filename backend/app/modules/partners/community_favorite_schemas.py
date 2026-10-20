from pydantic import BaseModel

from app.modules.partners.directory_schemas import CommunityCardResponse


class CommunityFavoriteStatusResponse(BaseModel):
    community_ids: list[int]


class CommunityFavoritePageResponse(BaseModel):
    items: list[CommunityCardResponse]
    next_cursor: int | None
