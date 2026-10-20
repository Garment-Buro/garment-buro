import base64
import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.partners.directory_repository import CommunityDirectoryRepository
from app.modules.partners.directory_schemas import (
    CommunityCardResponse,
    CommunityPageResponse,
    CommunityQuery,
)


class InvalidCommunityCursor(ValueError):
    pass


class CommunityPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(strict=True, ge=1, le=1)
    id: int = Field(strict=True, gt=0, le=2_147_483_647)
    title: str = Field(max_length=255, pattern=r"^[^\x00]*$")
    filters: str = Field(pattern=r"^[a-f0-9]{64}$")


class CommunityDirectoryService:
    def __init__(self, repository: CommunityDirectoryRepository | None = None):
        self.repository = repository or CommunityDirectoryRepository()

    async def list_page(
        self, session: AsyncSession, *, query: CommunityQuery
    ) -> CommunityPageResponse:
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "scope": "communities:unicode-v2",
                    "query": query.query.strip(),
                    "sort": query.sort,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        position = None
        if query.cursor is not None:
            try:
                position = CommunityPosition.model_validate_json(
                    base64.b64decode(
                        query.cursor,
                        altchars=b"-_",
                        validate=True,
                    )
                )
                if position.filters != fingerprint:
                    raise InvalidCommunityCursor
            except (ValueError, ValidationError) as error:
                raise InvalidCommunityCursor(
                    "Invalid cursor for these community filters"
                ) from error
        rows = await self.repository.list_page(
            session,
            query=query,
            after_id=position.id if position else None,
            after_title=position.title if position else None,
        )
        page = rows[: query.limit]
        cursor = None
        if len(rows) > query.limit:
            cursor = base64.urlsafe_b64encode(
                CommunityPosition(
                    version=1,
                    id=page[-1]["id"],
                    title=page[-1]["title"],
                    filters=fingerprint,
                )
                .model_dump_json()
                .encode()
            ).decode()
        return CommunityPageResponse(
            items=[CommunityCardResponse.model_validate(row) for row in page],
            next_cursor=cursor,
        )
