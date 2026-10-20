import base64
import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.customer_writes import lock_active_customer
from app.modules.public_profiles.models import PublicUserProfile
from app.modules.public_profiles.repository import PublicProfileRepository
from app.modules.public_profiles.schemas import (
    OwnPublicProfileResponse,
    PeoplePageResponse,
    PeopleQuery,
    PublicProfileResponse,
    PublicProfileWrite,
)


class ProfileConflictError(Exception):
    pass


class ProfileUnavailableError(Exception):
    pass


class InvalidPeopleCursor(ValueError):
    pass


class PeoplePosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(strict=True, ge=1, le=1)
    id: int = Field(strict=True, gt=0, le=2_147_483_647)
    name: str = Field(max_length=120, pattern=r"^[^\x00]*$")
    filters: str = Field(pattern=r"^[a-f0-9]{64}$")


class PublicProfileService:
    def __init__(self, repository: PublicProfileRepository | None = None):
        self.repository = repository or PublicProfileRepository()

    async def own(self, session: AsyncSession, user_id: int):
        profile = await self.repository.own(session, user_id)
        return OwnPublicProfileResponse.model_validate(profile) if profile else None

    async def lock_owned(
        self,
        session: AsyncSession,
        user_id: int,
        expected_version: int,
        *,
        must_exist: bool = False,
    ) -> PublicUserProfile | None:
        if not await lock_active_customer(session, user_id):
            raise ProfileUnavailableError
        profile = await self.repository.own(session, user_id, lock=True)
        if must_exist and profile is None:
            raise ProfileUnavailableError
        if expected_version != (profile.version if profile else 0):
            raise ProfileConflictError
        return profile

    async def save(self, session: AsyncSession, user_id: int, body: PublicProfileWrite):
        profile = await self.lock_owned(session, user_id, body.version)
        if profile is None:
            profile = PublicUserProfile(user_id=user_id)
            session.add(profile)
        for key, value in body.model_dump(exclude={"version"}).items():
            setattr(profile, key, value)
        profile.version = body.version + 1
        await session.flush()
        return OwnPublicProfileResponse.model_validate(profile)

    async def public(self, session: AsyncSession, slug: str):
        profile = await self.repository.public(session, slug)
        if profile is None:
            raise ProfileUnavailableError
        return PublicProfileResponse.model_validate(profile)

    async def remove_avatar(self, session: AsyncSession, user_id: int, expected_version: int):
        profile = await self.lock_owned(session, user_id, expected_version, must_exist=True)
        assert profile is not None
        await self.repository.detach_avatar(session, profile)
        profile.version += 1
        await session.flush()
        return OwnPublicProfileResponse.model_validate(profile)

    async def list_page(self, session: AsyncSession, query: PeopleQuery):
        fingerprint = hashlib.sha256(
            json.dumps(
                {"scope": "people:unicode-v2", "query": query.query.strip(), "sort": query.sort},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        position = None
        if query.cursor is not None:
            try:
                position = PeoplePosition.model_validate_json(
                    base64.b64decode(query.cursor, altchars=b"-_", validate=True)
                )
                if position.filters != fingerprint:
                    raise InvalidPeopleCursor
            except (ValueError, ValidationError) as error:
                raise InvalidPeopleCursor("Invalid cursor for these people filters") from error
        rows = await self.repository.list_page(
            session,
            query,
            after_id=position.id if position else None,
            after_name=position.name if position else None,
        )
        page = rows[: query.limit]
        cursor = None
        if len(rows) > query.limit:
            cursor = base64.urlsafe_b64encode(
                PeoplePosition(
                    version=1, id=page[-1]["id"], name=page[-1]["display_name"], filters=fingerprint
                )
                .model_dump_json()
                .encode()
            ).decode()
        return PeoplePageResponse(
            items=[PublicProfileResponse.model_validate(row) for row in page], next_cursor=cursor
        )
