from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, event, select

from app.db.session import DatabaseManager
from app.factory import create_app
from app.modules.catalog.models import Product, ProductCategory
from app.modules.identity.models import User
from app.modules.partners.models import PartnerLanding, PartnerProfile
from app.observability.logging import request_id_context
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.postgres_schema import migrate

PUBLIC = "/api/communities"
FAVORITES = "/api/profile/community-favorites"


@pytest.fixture(params=["sqlite", "postgres"])
def communities_setup(tmp_path: Path, request):
    postgres = request.param == "postgres"
    if postgres and not os.getenv("SCHEMA_TEST_POSTGRES_URL"):
        pytest.skip("Requires disposable PostgreSQL test database")
    url = (
        os.environ["SCHEMA_TEST_POSTGRES_URL"]
        if postgres
        else f"sqlite+aiosqlite:///{tmp_path / 'communities.db'}"
    )
    if postgres:
        from sqlalchemy import make_url

        assert (make_url(url).database or "").startswith("test_")
        migrate(url, "upgrade", "head")
    settings = favorite_settings(url).model_copy(
        update={
            "partner_program_enabled": True,
            "partner_attribution_secret": SecretStr("s" * 32),
        }
    )
    products, tokens, users = asyncio.run(seed_favorites(settings, create_schema=not postgres))

    async def seed():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                owners = [
                    User(
                        internal_identity=uuid4().hex,
                        first_name="Private name",
                        phone="Private phone",
                        status=status,
                    )
                    for status in ("active", "active", "active", "blocked", "deleted")
                ]
                session.add_all(owners)
                await session.flush()
                profiles = [
                    PartnerProfile(
                        user_id=owner.id,
                        code=uuid4().hex,
                        display_name=f"Public owner {index}",
                        status=status,
                        commission_bps=1000,
                    )
                    for index, (owner, status) in enumerate(
                        zip(
                            owners,
                            ("active", "invited", "suspended", "active", "active"),
                            strict=True,
                        )
                    )
                ]
                session.add_all(profiles)
                await session.flush()
                rows = []
                for index, (title, profile_index, status) in enumerate(
                    [
                        ("Running 100%", 0, "published"),
                        ("Running_club", 0, "published"),
                        ("Box Club", 0, "published"),
                        ("Draft", 0, "draft"),
                        ("Archived", 0, "archived"),
                        ("Invited", 1, "published"),
                        ("Suspended", 2, "published"),
                        ("Blocked", 3, "published"),
                        ("Deleted", 4, "published"),
                    ]
                ):
                    rows.append(
                        PartnerLanding(
                            partner_id=profiles[profile_index].id,
                            slug=f"community-{uuid4().hex}",
                            title=title,
                            headline=title,
                            description="Public description",
                            cta_label="Открыть",
                            cta_href="/constructor",
                            image_url="https://media.example.test/community.webp"
                            if index == 0
                            else None,
                            content={"story_body": "Never load this in directory"},
                            status=status,
                        )
                    )
                session.add_all(rows)
                await session.commit()
                return (
                    [row.id for row in rows],
                    [row.slug for row in rows],
                    [owner.id for owner in owners],
                    [profile.id for profile in profiles],
                )
        finally:
            await database.shutdown()

    ids, slugs, owners, profiles = asyncio.run(seed())

    async def cleanup():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                await session.execute(delete(PartnerLanding).where(PartnerLanding.id.in_(ids)))
                await session.execute(delete(PartnerProfile).where(PartnerProfile.id.in_(profiles)))
                category_ids = list(
                    (
                        await session.scalars(
                            select(Product.category_id).where(
                                Product.id.in_(products),
                                Product.category_id.is_not(None),
                            )
                        )
                    ).all()
                )
                await session.execute(delete(Product).where(Product.id.in_(products)))
                await session.execute(
                    delete(ProductCategory).where(ProductCategory.id.in_(category_ids))
                )
                await session.execute(delete(User).where(User.id.in_([*users, *owners])))
                await session.commit()
        finally:
            await database.shutdown()

    try:
        with TestClient(create_app(settings=settings)) as client:
            yield client, ids, slugs, tokens, owners
    finally:
        if postgres:
            asyncio.run(cleanup())


def test_directory_lists_only_unique_published_landings_and_public_fields(communities_setup):
    client, ids, slugs, _, _ = communities_setup
    response = client.get(PUBLIC)
    assert response.status_code == 200
    data = response.json()
    assert [row["id"] for row in data["items"]] == ids[:3][::-1]
    assert data["next_cursor"] is None
    assert data["items"][-1] == {
        "id": ids[0],
        "slug": slugs[0],
        "title": "Running 100%",
        "description": "Public description",
        "owner_name": "Public owner 0",
        "image_url": "https://media.example.test/community.webp",
    }
    assert "Private" not in response.text
    assert "private_editor_field" not in response.text


@pytest.mark.parametrize("sort, order", [("newest", [2, 1, 0]), ("name", [2, 0, 1])])
def test_directory_keyset_pages_never_repeat_cards(communities_setup, sort, order):
    client, ids, _, _, _ = communities_setup
    first = client.get(PUBLIC, params={"sort": sort, "limit": 2})
    assert first.status_code == 200
    assert [row["id"] for row in first.json()["items"]] == [ids[index] for index in order[:2]]
    cursor = first.json()["next_cursor"]
    assert cursor
    second = client.get(PUBLIC, params={"sort": sort, "limit": 2, "cursor": cursor})
    assert second.status_code == 200
    assert [row["id"] for row in second.json()["items"]] == [ids[order[2]]]
    assert second.json()["next_cursor"] is None
    assert (
        client.get(
            PUBLIC, params={"sort": sort, "query": "different", "cursor": cursor}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "query, indexes", [("%", [0]), ("_", [1]), ("Running", [1, 0]), ("missing", [])]
)
def test_directory_search_is_literal_and_filtered_in_sql(communities_setup, query, indexes):
    client, ids, _, _, _ = communities_setup
    response = client.get(PUBLIC, params={"query": query})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["items"]] == [ids[index] for index in indexes]


def test_directory_uses_one_bounded_projection_without_content_or_products(communities_setup):
    client, _, _, _, _ = communities_setup
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if request_id_context.get() == "community-projection":
            statements.append(statement.lower())

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get(
            PUBLIC, headers={"X-Request-ID": "community-projection"}, params={"limit": 2}
        )
        assert response.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 1
    assert "limit" in statements[0]
    assert "partner_landings.content" not in statements[0]
    assert "products" not in statements[0]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"query": "q" * 201},
        {"sort": "invalid"},
        {"cursor": "invalid"},
    ],
)
def test_directory_rejects_invalid_query(communities_setup, params):
    client, _, _, _, _ = communities_setup
    assert client.get(PUBLIC, params=params).status_code == 422


def test_public_slug_cannot_bypass_owner_publication_policy(communities_setup):
    client, _, slugs, _, _ = communities_setup
    assert client.get(f"/api/partner/landings/{slugs[0]}").status_code == 200
    for slug in slugs[3:]:
        assert client.get(f"/api/partner/landings/{slug}").status_code == 404


def test_community_favorites_require_a_real_customer(communities_setup):
    client, ids, _, _, _ = communities_setup
    for method, path in [
        ("get", FAVORITES),
        ("get", f"{FAVORITES}/status?community_ids={ids[0]}"),
        ("put", f"{FAVORITES}/{ids[0]}"),
        ("delete", f"{FAVORITES}/{ids[0]}"),
    ]:
        assert getattr(client, method)(path).status_code == 401


def test_community_favorites_persist_are_idempotent_and_are_private_to_the_customer(
    communities_setup,
):
    client, ids, _, tokens, _ = communities_setup
    owner = tokens[0]
    other = tokens[1]
    for identity in ids[:3]:
        for _ in range(2):
            assert client.put(f"{FAVORITES}/{identity}", headers=owner).status_code == 204
    status = client.get(f"{FAVORITES}/status", params={"community_ids": ids[:3]}, headers=owner)
    assert status.status_code == 200
    assert status.json() == {"community_ids": ids[:3]}
    assert status.headers["Cache-Control"] == "no-store"
    assert client.get(
        f"{FAVORITES}/status", params={"community_ids": ids[:3]}, headers=other
    ).json() == {"community_ids": []}
    assert client.get(FAVORITES, headers=other).json() == {"items": [], "next_cursor": None}
    assert client.get("/api/profile/favorites", headers=owner).json() == {
        "items": [],
        "next_cursor": None,
    }
    first = client.get(FAVORITES, params={"limit": 2}, headers=owner)
    assert [row["id"] for row in first.json()["items"]] == [ids[2], ids[1]]
    cursor = first.json()["next_cursor"]
    assert cursor
    last = client.get(FAVORITES, params={"limit": 2, "cursor": cursor}, headers=owner)
    assert [row["id"] for row in last.json()["items"]] == [ids[0]]
    assert last.json()["next_cursor"] is None
    with TestClient(create_app(settings=client.app.state.settings)) as restarted:
        assert [
            row["id"] for row in restarted.get(FAVORITES, headers=owner).json()["items"]
        ] == ids[:3][::-1]
    assert client.delete(f"{FAVORITES}/{ids[0]}", headers=other).status_code == 204
    assert len(client.get(FAVORITES, headers=owner).json()["items"]) == 3
    for _ in range(2):
        assert client.delete(f"{FAVORITES}/{ids[0]}", headers=owner).status_code == 204
    assert [row["id"] for row in client.get(FAVORITES, headers=owner).json()["items"]] == [
        ids[2],
        ids[1],
    ]


def test_unavailable_community_cannot_be_saved(communities_setup):
    client, ids, _, tokens, _ = communities_setup
    owner = tokens[0]
    for identity in [*ids[3:], 2_147_483_647]:
        assert client.put(f"{FAVORITES}/{identity}", headers=owner).status_code == 404


def test_unpublished_favorite_is_hidden_from_list_and_membership(communities_setup):
    client, ids, _, tokens, _ = communities_setup
    owner = tokens[0]
    assert client.put(f"{FAVORITES}/{ids[0]}", headers=owner).status_code == 204

    async def unpublish():
        from sqlalchemy import update

        async with client.app.state.database.session() as session:
            await session.execute(
                update(PartnerLanding).where(PartnerLanding.id == ids[0]).values(status="draft")
            )
            await session.commit()

    client.portal.call(unpublish)
    assert client.get(FAVORITES, headers=owner).json() == {"items": [], "next_cursor": None}
    assert client.get(
        f"{FAVORITES}/status", params={"community_ids": ids[:3]}, headers=owner
    ).json() == {"community_ids": []}
    assert client.delete(f"{FAVORITES}/{ids[0]}", headers=owner).status_code == 204


def test_deleted_customer_community_favorites_are_purged_by_the_existing_lifecycle(
    communities_setup,
):
    client, ids, _, tokens, _ = communities_setup
    assert client.put(f"{FAVORITES}/{ids[0]}", headers=tokens[0]).status_code == 204
    assert client.delete("/api/auth/me", headers=tokens[0]).status_code == 200

    async def purge():
        from sqlalchemy import func

        from app.modules.customer_projects.lifecycle_repository import ProjectLifecycleRepository
        from app.modules.partners.community_favorite_models import UserCommunityFavorite

        async with client.app.state.database.session() as session:
            assert (
                await session.scalar(select(func.count()).select_from(UserCommunityFavorite)) == 1
            )
            dry_counts = await ProjectLifecycleRepository().purge_deleted_data(
                session, limit=10, dry_run=True
            )
            assert dry_counts == (0, 1, 0)
            assert (
                await session.scalar(select(func.count()).select_from(UserCommunityFavorite)) == 1
            )
            assert await ProjectLifecycleRepository().purge_deleted_data(
                session, limit=10, dry_run=False
            ) == (0, 1, 0)
            await session.commit()
            assert (
                await session.scalar(select(func.count()).select_from(UserCommunityFavorite)) == 0
            )

    client.portal.call(purge)


@pytest.mark.parametrize(
    "title", ["😀" * 255, "a" + "\x01" * 253 + "z"], ids=["utf8", "json-escapes"]
)
def test_directory_can_follow_its_own_cursor_for_maximum_length_titles(communities_setup, title):
    client, ids, _, _, _ = communities_setup

    async def rename():
        from sqlalchemy import update

        async with client.app.state.database.session() as session:
            await session.execute(
                update(PartnerLanding).where(PartnerLanding.id.in_(ids[:2])).values(title=title)
            )
            await session.commit()

    client.portal.call(rename)
    for sort in ("newest", "name"):
        cursor, seen = None, []
        for _ in range(3):
            params = {"sort": sort, "limit": 1}
            if cursor:
                params["cursor"] = cursor
            response = client.get(PUBLIC, params=params)
            assert response.status_code == 200
            seen.extend(row["id"] for row in response.json()["items"])
            cursor = response.json()["next_cursor"]
        assert len(seen) == len(set(seen)) == 3
        assert cursor is None


def test_directory_rejects_search_strings_with_nul(communities_setup):
    client, _, _, _, _ = communities_setup
    assert client.get(PUBLIC, params={"query": "club\x00"}).status_code == 422


def test_directory_rejects_a_cursor_containing_a_nul_title(communities_setup):
    client, _, _, _, _ = communities_setup
    params = {"sort": "name", "limit": 1}
    response = client.get(PUBLIC, params=params)
    assert response.status_code == 200
    payload = json.loads(base64.urlsafe_b64decode(response.json()["next_cursor"]))
    payload["title"] = "club\x00"
    params["cursor"] = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    assert client.get(PUBLIC, params=params).status_code == 422
