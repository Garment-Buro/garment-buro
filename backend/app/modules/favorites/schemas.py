from datetime import datetime

from pydantic import BaseModel


class FavoriteItemResponse(BaseModel):
    product_id: int
    saved_at: datetime


class FavoritePageResponse(BaseModel):
    items: list[FavoriteItemResponse]
    next_cursor: int | None


class FavoriteStatusResponse(BaseModel):
    product_ids: list[int]
