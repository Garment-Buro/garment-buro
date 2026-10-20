from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, update

from app.factory import create_app
from app.modules.catalog.models import Product, ProductCategory
from app.modules.identity.models import User
from app.observability.logging import request_id_context
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.postgres_schema import migrate

PUBLIC = "/api/people"
OWN = "/api/profile/public"


def _people_setup(tmp_path: Path, postgres: bool):
    if postgres and not os.getenv("SCHEMA_TEST_POSTGRES_URL"):
        pytest.skip("Requires disposable PostgreSQL test database")
    url = (
        os.environ["SCHEMA_TEST_POSTGRES_URL"]
        if postgres
        else f"sqlite+aiosqlite:///{tmp_path / 'people.db'}"
    )
    if postgres:
        from sqlalchemy import make_url

        assert (make_url(url).database or "").startswith("test_")
        migrate(url, "upgrade", "head")
    settings = favorite_settings(url)
    products, tokens, users = asyncio.run(seed_favorites(settings, create_schema=not postgres))
    with TestClient(create_app(settings=settings)) as client:
        try:
            yield client, tokens, users
        finally:

            async def cleanup():
                async with client.app.state.database.session() as session:
                    category_ids = list(
                        await session.scalars(
                            select(Product.category_id).where(
                                Product.id.in_(products), Product.category_id.is_not(None)
                            )
                        )
                    )
                    await session.execute(delete(Product).where(Product.id.in_(products)))
                    await session.execute(
                        delete(ProductCategory).where(ProductCategory.id.in_(category_ids))
                    )
                    await session.execute(delete(User).where(User.id.in_(users)))
                    await session.commit()

            client.portal.call(cleanup)


@pytest.fixture(params=["sqlite", "postgres"])
def people_setup(tmp_path: Path, request):
    yield from _people_setup(tmp_path, request.param == "postgres")


@pytest.fixture
def people_postgres_setup(tmp_path: Path):
    yield from _people_setup(tmp_path, True)


def profile(**changes):
    return {
        "slug": "person-" + uuid4().hex[:12],
        "display_name": "Публичное имя",
        "bio": "Описание пользователя",
        "is_published": False,
        "version": 0,
        **changes,
    }


def save(client, token, body):
    response = client.put(OWN, headers=token, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_profile_is_absent_until_created_and_requires_authentication(people_setup):
    client, tokens, _ = people_setup
    assert client.get(OWN).status_code == 401
    assert client.put(OWN, json=profile()).status_code == 401
    response = client.get(OWN, headers=tokens[0])
    assert response.status_code == 200
    assert response.json() is None
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get(PUBLIC).json() == {"items": [], "next_cursor": None}


def test_own_profile_is_separate_private_and_persists_after_restart(people_setup):
    client, tokens, _ = people_setup
    private_before = client.get("/api/auth/me", headers=tokens[0]).json()
    body = profile(display_name="  Моё публичное имя  ", bio="  Моя история  ")
    created = save(client, tokens[0], body)
    assert created == {
        "id": created["id"],
        **body,
        "display_name": "Моё публичное имя",
        "bio": "Моя история",
        "version": 1,
        "avatar_id": None,
    }
    assert client.get(OWN, headers=tokens[1]).json() is None
    assert client.get(f"{PUBLIC}/{body['slug']}").status_code == 404
    assert client.get(PUBLIC).json()["items"] == []
    assert client.get("/api/auth/me", headers=tokens[0]).json() == private_before
    with TestClient(create_app(settings=client.app.state.settings)) as restarted:
        assert restarted.get(OWN, headers=tokens[0]).json() == created


def test_publication_and_unpublication_apply_to_directory_and_direct_read(people_setup):
    client, tokens, _ = people_setup
    created = save(client, tokens[0], profile(is_published=True))
    public = {key: created[key] for key in ("id", "slug", "display_name", "bio", "avatar_id")}
    response = client.get(f"{PUBLIC}/{created['slug']}")
    assert response.status_code == 200
    assert response.json() == public
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get(PUBLIC).json()["items"] == [public]
    changed = save(
        client,
        tokens[0],
        {
            key: value
            for key, value in {**created, "is_published": False}.items()
            if key not in {"id", "avatar_id"}
        },
    )
    assert changed["version"] == 2
    hidden = client.get(f"{PUBLIC}/{created['slug']}")
    assert hidden.status_code == 404
    assert hidden.headers.get("Cache-Control") == "no-store"
    assert client.get(PUBLIC).json()["items"] == []
    assert client.get(OWN, headers=tokens[0]).json() == changed


def test_stale_version_duplicate_slug_and_foreign_ownership_are_rejected(people_setup):
    client, tokens, _ = people_setup
    created = save(client, tokens[0], profile(is_published=True))
    body = {key: value for key, value in created.items() if key not in {"id", "avatar_id"}}
    assert client.put(OWN, headers=tokens[0], json={**body, "version": 0}).status_code == 409
    assert client.put(OWN, headers=tokens[1], json={**body, "version": 0}).status_code == 409
    assert client.put(OWN, headers=tokens[1], json={**body, "user_id": 1}).status_code == 422
    assert client.get(OWN, headers=tokens[0]).json() == created
    assert client.get(OWN, headers=tokens[1]).json() is None
    assert client.put(OWN, headers=tokens[1], json=profile(version=1)).status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        {"slug": "../bad"},
        {"slug": "UpperCase"},
        {"slug": "ab"},
        {"slug": "a" * 65},
        {"display_name": "   "},
        {"display_name": "n" * 121},
        {"bio": "x" * 2001},
        {"bio": "bad\x00input"},
        {"email": "private@example.test"},
        {"version": -1},
        {"is_published": "false"},
    ],
)
def test_profile_write_validates_public_fields_without_mass_assignment(people_setup, change):
    client, tokens, _ = people_setup
    assert client.put(OWN, headers=tokens[0], json=profile(**change)).status_code == 422
    assert client.get(OWN, headers=tokens[0]).json() is None


@pytest.mark.parametrize("status", ["blocked", "deleted"])
def test_unavailable_account_hides_public_profile_and_prevents_owner_write(people_setup, status):
    client, tokens, users = people_setup
    created = save(client, tokens[0], profile(is_published=True))

    async def change_status():
        async with client.app.state.database.session() as session:
            await session.execute(update(User).where(User.id == users[0]).values(status=status))
            await session.commit()

    client.portal.call(change_status)
    assert client.get(f"{PUBLIC}/{created['slug']}").status_code == 404
    assert client.get(PUBLIC).json()["items"] == []
    assert (
        client.put(
            OWN,
            headers=tokens[0],
            json={key: value for key, value in created.items() if key not in {"id", "avatar_id"}},
        ).status_code
        == 401
    )


def test_directory_has_bounded_scalar_sql_literal_search_and_query_bound_cursor(people_setup):
    client, tokens, _ = people_setup
    first = save(client, tokens[0], profile(display_name="Name 100%", is_published=True))
    second = save(client, tokens[1], profile(display_name="Name_under", is_published=True))
    statements = []

    def capture(connection, cursor, statement, parameters, context, many):
        if request_id_context.get() and statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get(PUBLIC, params={"limit": 1})
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert len(statements) == 1
    assert "LIMIT" in statements[0].upper()
    assert "users.email" not in statements[0] and "users.phone" not in statements[0]
    assert response.json()["items"][0]["id"] == second["id"]
    cursor = response.json()["next_cursor"]
    assert cursor
    last = client.get(PUBLIC, params={"limit": 1, "cursor": cursor}).json()
    assert [item["id"] for item in last["items"]] == [first["id"]]
    assert last["next_cursor"] is None
    assert client.get(PUBLIC, params={"cursor": cursor, "query": "Name"}).status_code == 422
    assert client.get(PUBLIC, params={"cursor": cursor, "sort": "name"}).status_code == 422
    assert [row["id"] for row in client.get(PUBLIC, params={"query": "%"}).json()["items"]] == [
        first["id"]
    ]
    assert [row["id"] for row in client.get(PUBLIC, params={"query": "_"}).json()["items"]] == [
        second["id"]
    ]
    assert client.get(PUBLIC, params={"query": "missing"}).json() == {
        "items": [],
        "next_cursor": None,
    }
    by_name = client.get(PUBLIC, params={"sort": "name", "limit": 1}).json()
    assert by_name["items"][0]["id"] == first["id"]
    assert (
        client.get(PUBLIC, params={"sort": "name", "cursor": by_name["next_cursor"]}).json()[
            "items"
        ][0]["id"]
        == second["id"]
    )
    position = json.loads(base64.urlsafe_b64decode(cursor))
    position["name"] = "bad\x00position"
    poisoned = base64.urlsafe_b64encode(json.dumps(position).encode()).decode()
    assert client.get(PUBLIC, params={"cursor": poisoned}).status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"sort": "wrong"},
        {"query": "x" * 201},
        {"query": "bad\x00"},
        {"cursor": "bad"},
        {"cursor": "x" * 4097},
    ],
)
def test_directory_rejects_invalid_parameters(people_setup, params):
    client, _, _ = people_setup
    assert client.get(PUBLIC, params=params).status_code == 422


def test_deleted_account_profile_is_removed_by_bounded_lifecycle(people_setup):
    client, tokens, _ = people_setup
    created = save(client, tokens[0], profile(is_published=True))
    assert client.delete("/api/auth/me", headers=tokens[0]).status_code == 200

    async def purge():
        from app.modules.customer_projects.lifecycle_repository import ProjectLifecycleRepository
        from app.modules.public_profiles.models import PublicUserProfile

        async with client.app.state.database.session() as session:
            repository = ProjectLifecycleRepository()
            assert await repository.purge_deleted_data(session, limit=1, dry_run=True) == (0, 0, 1)
            assert await session.get(PublicUserProfile, created["id"]) is not None
            assert await repository.purge_deleted_data(session, limit=1, dry_run=False) == (0, 0, 1)
            await session.commit()
        async with client.app.state.database.session() as session:
            assert await session.get(PublicUserProfile, created["id"]) is None

    client.portal.call(purge)


def test_postgres_concurrent_profile_writes_cannot_silently_replace_each_other(
    people_postgres_setup,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client, tokens, _ = people_postgres_setup
    created = save(client, tokens[0], profile(is_published=True))
    body = {key: value for key, value in created.items() if key not in {"id", "avatar_id"}}
    barrier = Barrier(2)

    def write(name):
        barrier.wait(timeout=10)
        return client.put(OWN, headers=tokens[0], json={**body, "display_name": name})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(write, ["Concurrent one", "Concurrent two"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert winner["version"] == 2
    assert client.get(OWN, headers=tokens[0]).json() == winner


@pytest.mark.parametrize("same_account", [True, False])
def test_postgres_concurrent_profile_creation_and_slug_claim_have_one_winner(
    people_postgres_setup, same_account
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client, tokens, _ = people_postgres_setup
    body = profile(is_published=True)
    headers = (tokens[0], tokens[0] if same_account else tokens[1])
    barrier = Barrier(2)

    def write(index):
        barrier.wait(timeout=10)
        return client.put(OWN, headers=headers[index], json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(write, [0, 1]))
    assert sorted(statuses) == [200, 409]
