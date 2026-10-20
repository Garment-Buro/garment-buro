import base64
import hashlib

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.partners.admin_directory_repository import AdminLandingRepository
from app.modules.partners.admin_directory_schemas import (
    AdminLandingCard,
    AdminLandingPage,
    AdminLandingQuery,
)


class InvalidAdminLandingCursor(ValueError):
    pass


class AdminLandingPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(ge=1, le=1)
    id: int = Field(gt=0, le=2_147_483_647)
    filters: str = Field(pattern=r"^[a-f0-9]{64}$")


class AdminLandingService:
    @staticmethod
    async def list_page(session: AsyncSession, query: AdminLandingQuery) -> AdminLandingPage:
        fingerprint = hashlib.sha256(
            query.model_dump_json(exclude={"cursor", "limit"}).encode()
        ).hexdigest()
        after_id = None
        if query.cursor is not None:
            try:
                position = AdminLandingPosition.model_validate_json(
                    base64.b64decode(query.cursor, altchars=b"-_", validate=True)
                )
                if position.filters != fingerprint:
                    raise ValueError("Different landing filters")
                after_id = position.id
            except (ValueError, ValidationError) as error:
                raise InvalidAdminLandingCursor(
                    "Invalid cursor for these landing filters"
                ) from error
        records = await AdminLandingRepository.list_page(session, query, after_id)
        selected = records[: query.limit]
        cursor = None
        if len(records) > query.limit:
            cursor = base64.urlsafe_b64encode(
                AdminLandingPosition(
                    version=1,
                    id=selected[-1]["id"],
                    filters=fingerprint,
                )
                .model_dump_json()
                .encode()
            ).decode()
        return AdminLandingPage(
            items=[AdminLandingCard.model_validate(row) for row in selected], next_cursor=cursor
        )
