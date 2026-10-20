"""Small catalog projections; no ORM relationships or storage credentials."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogMediaView:
    id: int
    bucket_name: str
    object_key: str
    content_type: str
    status: str
    is_public: bool


@dataclass(frozen=True, slots=True)
class CatalogMediaLinkView:
    id: int
    owner_id: int
    role: str
    sort_order: int
    media: CatalogMediaView
