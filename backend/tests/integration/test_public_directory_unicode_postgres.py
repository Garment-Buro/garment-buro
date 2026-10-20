from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import models as database_models  # noqa: F401
from app.db.base import Base
from app.modules.identity.models import User
from app.modules.media.models import MediaObject
from app.modules.partners.directory_schemas import CommunityQuery
from app.modules.partners.directory_service import CommunityDirectoryService, InvalidCommunityCursor
from app.modules.partners.models import PartnerLanding, PartnerProfile
from app.modules.public_profiles.models import PublicUserProfile
from app.modules.public_profiles.schemas import PeopleQuery
from app.modules.public_profiles.service import InvalidPeopleCursor, PublicProfileService
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)
NAMES = ["АНЯ", "аня", "БОРИС", "борис", "ЁЖ", "ёж", "ŽOFIE", "žofie", "Name100%_\\"]


@asynccontextmanager
async def directories(url):
    schema = "test_unicode_" + uuid4().hex
    engine = create_async_engine(url)
    scoped = engine.execution_options(schema_translate_map={None: schema})
    sessions = async_sessionmaker(scoped, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with scoped.begin() as connection:
            await connection.run_sync(
                lambda conn: Base.metadata.create_all(
                    conn,
                    tables=[
                        User.__table__,
                        MediaObject.__table__,
                        PublicUserProfile.__table__,
                        PartnerProfile.__table__,
                        PartnerLanding.__table__,
                    ],
                )
            )
        async with sessions() as session:
            rows = {"people": [], "communities": []}
            for index, name in enumerate(NAMES):
                user = await session.scalar(
                    insert(User).values(internal_identity=uuid4().hex).returning(User.id)
                )
                person = await session.scalar(
                    insert(PublicUserProfile)
                    .values(
                        user_id=user,
                        slug=f"person-{index}",
                        display_name=name,
                        bio="РУЧНОЕ ОПИСАНИЕ",
                        is_published=True,
                    )
                    .returning(PublicUserProfile.id)
                )
                rows["people"].append({"id": person, "name": name})
                if index == 0:
                    partner = await session.scalar(
                        insert(PartnerProfile)
                        .values(
                            user_id=user,
                            code="owner",
                            display_name="СОЗДАТЕЛЬ",
                            status="active",
                            commission_bps=1000,
                        )
                        .returning(PartnerProfile.id)
                    )
                landing = await session.scalar(
                    insert(PartnerLanding)
                    .values(
                        partner_id=partner,
                        slug=f"community-{index}",
                        title=name,
                        headline=name,
                        description="РУЧНОЕ ОПИСАНИЕ",
                        cta_label="Открыть",
                        cta_href="/constructor",
                        content={},
                        status="published",
                    )
                    .returning(PartnerLanding.id)
                )
                rows["communities"].append({"id": landing, "name": name})
            await session.commit()
        yield sessions, rows
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


async def read(session, domain, **parameters):
    if domain == "people":
        return await PublicProfileService().list_page(session, PeopleQuery(**parameters))
    return await CommunityDirectoryService().list_page(session, query=CommunityQuery(**parameters))


@pytest.mark.parametrize("domain", ["people", "communities"])
def test_unicode_search_is_case_independent_and_wildcards_remain_literal(postgres_url, domain):
    async def scenario():
        async with directories(postgres_url) as (sessions, rows), sessions() as session:
            for query, expected in [
                ("аня", {0, 1}),
                ("Ёж", {4, 5}),
                ("žofie", {6, 7}),
                ("описание", set(range(9))),
                ("%", {8}),
                ("_", {8}),
                ("\\", {8}),
            ]:
                page = await read(session, domain, query=query)
                assert {item.id for item in page.items} == {
                    rows[domain][i]["id"] for i in expected
                }, query
            if domain == "communities":
                page = await read(session, domain, query="создатель")
                assert len(page.items) == 9

    asyncio.run(scenario())


@pytest.mark.parametrize("domain", ["people", "communities"])
def test_name_keyset_uses_the_same_unicode_order_and_tie_breaker(postgres_url, domain):
    async def scenario():
        async with directories(postgres_url) as (sessions, rows), sessions() as session:
            expected = sorted(rows[domain], key=lambda row: (row["name"].lower(), row["id"]))
            ids, cursor = [], None
            for _ in range(len(NAMES)):
                page = await read(session, domain, sort="name", limit=1, cursor=cursor)
                assert len(page.items) == 1
                ids.append(page.items[0].id)
                cursor = page.next_cursor
            assert cursor is None
            assert ids == [row["id"] for row in expected]

    asyncio.run(scenario())


@pytest.mark.parametrize("domain", ["people", "communities"])
def test_cursor_from_previous_case_order_is_rejected(postgres_url, domain):
    async def scenario():
        async with directories(postgres_url) as (sessions, rows), sessions() as session:
            filters = {"query": "", "sort": "name"}
            if domain == "people":
                filters["scope"] = "people:v1"
            position = {
                "version": 1,
                "id": rows[domain][0]["id"],
                "name" if domain == "people" else "title": NAMES[0],
                "filters": hashlib.sha256(json.dumps(filters, sort_keys=True).encode()).hexdigest(),
            }
            cursor = base64.urlsafe_b64encode(json.dumps(position).encode()).decode()
            with pytest.raises(
                InvalidPeopleCursor if domain == "people" else InvalidCommunityCursor
            ):
                await read(session, domain, sort="name", cursor=cursor)

    asyncio.run(scenario())


def test_unicode_directory_index_migration_preserves_existing_rows_on_round_trip(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20261017_0066")
    ids = {}

    async def snapshot(action):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                if action == "seed":
                    ids["user"] = await connection.scalar(
                        insert(User).values(internal_identity=uuid4().hex).returning(User.id)
                    )
                    ids["profile"] = await connection.scalar(
                        insert(PublicUserProfile)
                        .values(
                            user_id=ids["user"],
                            slug=uuid4().hex,
                            display_name="АНЯ",
                            bio="Сохранить описание",
                            is_published=True,
                        )
                        .returning(PublicUserProfile.id)
                    )
                    ids["partner"] = await connection.scalar(
                        insert(PartnerProfile)
                        .values(
                            user_id=ids["user"],
                            code=uuid4().hex,
                            display_name="Владелец",
                            status="active",
                            commission_bps=1000,
                        )
                        .returning(PartnerProfile.id)
                    )
                    ids["landing"] = await connection.scalar(
                        insert(PartnerLanding)
                        .values(
                            partner_id=ids["partner"],
                            slug=uuid4().hex,
                            title="КОЛЛЕКЦИЯ",
                            headline="Сохранить заголовок",
                            description="Сохранить описание",
                            cta_label="Открыть",
                            cta_href="/constructor",
                            content={},
                            status="published",
                        )
                        .returning(PartnerLanding.id)
                    )
                if action == "cleanup":
                    await connection.execute(
                        delete(PartnerLanding).where(PartnerLanding.id == ids.get("landing"))
                    )
                    await connection.execute(
                        delete(PartnerProfile).where(PartnerProfile.id == ids.get("partner"))
                    )
                    await connection.execute(delete(User).where(User.id == ids.get("user")))
                    return
                person = (
                    await connection.execute(
                        select(PublicUserProfile.__table__).where(
                            PublicUserProfile.id == ids["profile"]
                        )
                    )
                ).one()
                landing = (
                    await connection.execute(
                        select(PartnerLanding.__table__).where(PartnerLanding.id == ids["landing"])
                    )
                ).one()
                indexes = dict(
                    (
                        await connection.execute(
                            text(
                                "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' "
                                "AND indexname IN ('ix_public_profiles_published_name', "
                                "'ix_partner_landings_status_name', 'ix_partner_landings_status')"
                            )
                        )
                    ).all()
                )
                return (tuple(person), tuple(landing)), indexes
        finally:
            await engine.dispose()

    try:
        before, old_indexes = asyncio.run(snapshot("seed"))
        assert "pg_c_utf8" not in old_indexes["ix_public_profiles_published_name"]
        assert "ix_partner_landings_status" in old_indexes
        migrate(postgres_url, "upgrade", "head")
        rows, indexes = asyncio.run(snapshot("read"))
        assert rows == before
        assert set(indexes) == {
            "ix_public_profiles_published_name",
            "ix_partner_landings_status_name",
        }
        assert all("pg_c_utf8" in definition for definition in indexes.values())
        migrate(postgres_url, "downgrade", "20261017_0066")
        assert asyncio.run(snapshot("read")) == (before, old_indexes)
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(snapshot("cleanup"))
