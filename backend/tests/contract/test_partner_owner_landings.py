"""Owner commands must never mutate another partner or silently overwrite an editor."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, event, select, update

from app.factory import create_app
from app.modules.catalog.models import Product, ProductCategory
from app.modules.identity.models import RoleName, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.partners.models import PartnerLanding, PartnerProfile
from app.modules.partners.schemas import PartnerLandingUpdateRequest
from app.modules.partners.service import PartnerLandingVersionConflictError, PartnerNotFoundError
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.postgres_schema import migrate

OWN = "/api/partner/own-landings"
PUBLIC = "/api/partner/landings"


def _setup(tmp_path, postgres):
    if postgres and not os.getenv("SCHEMA_TEST_POSTGRES_URL"):
        pytest.skip("Requires disposable PostgreSQL test database")
    url = (
        os.environ["SCHEMA_TEST_POSTGRES_URL"]
        if postgres
        else f"sqlite+aiosqlite:///{tmp_path / 'owner.db'}"
    )
    if postgres:
        from sqlalchemy import make_url

        assert (make_url(url).database or "").startswith("test_")
        migrate(url, "upgrade", "head")
    settings = favorite_settings(url).model_copy(
        update={"partner_program_enabled": True, "partner_attribution_secret": SecretStr("s" * 32)}
    )
    products, tokens, users = asyncio.run(seed_favorites(settings, create_schema=not postgres))
    with TestClient(create_app(settings=settings)) as client:

        async def profiles():
            async with client.app.state.database.session() as session:
                rows = [
                    PartnerProfile(
                        user_id=user_id,
                        code=uuid4().hex,
                        display_name=f"Owner {index}",
                        commission_bps=1000,
                        status="active",
                    )
                    for index, user_id in enumerate(users)
                ]
                session.add_all(rows)
                for user_id in users:
                    await client.app.state.partner_program_service.repository.assign_partner_role(
                        session, user_id=user_id, assigned_by_user_id=user_id
                    )
                await session.commit()
                return [row.id for row in rows]

        profiles_ids = client.portal.call(profiles)
        try:
            yield client, products, tokens, users, profiles_ids
        finally:

            async def cleanup():
                async with client.app.state.database.session() as session:
                    await session.execute(
                        delete(PartnerLanding).where(PartnerLanding.partner_id.in_(profiles_ids))
                    )
                    await session.execute(
                        delete(PartnerProfile).where(PartnerProfile.id.in_(profiles_ids))
                    )
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
def owners(tmp_path, request):
    yield from _setup(tmp_path, request.param == "postgres")


@pytest.fixture
def postgres_owners(tmp_path):
    yield from _setup(tmp_path, True)


def body(products, **changes):
    return {
        "slug": "owner-" + uuid4().hex,
        "title": "Коллекция автора",
        "headline": "Моя коллекция",
        "description": "Реальная подборка каталога",
        "cta_label": "Выбрать",
        "cta_href": "/constructor",
        "product_ids": [products[1], products[0]],
        **changes,
    }


def create(owners, **changes):
    client, products, tokens, _, _ = owners
    response = client.post(OWN, headers=tokens[0], json=body(products, **changes))
    assert response.status_code == 201, response.text
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()


def test_owner_create_is_private_ordered_and_persists_after_restart(owners):
    client, products, tokens, _, profiles = owners
    created = create(owners)
    assert created["partner_id"] == profiles[0]
    assert created["status"] == "draft"
    assert created["version"] == 1
    assert created["product_ids"] == [products[1], products[0]]
    assert client.get(f"{PUBLIC}/{created['slug']}").status_code == 404
    response = client.get(f"{OWN}/{created['id']}", headers=tokens[0])
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == created
    with TestClient(create_app(settings=client.app.state.settings)) as restarted:
        assert restarted.get(f"{OWN}/{created['id']}", headers=tokens[0]).json() == created


def test_owner_never_reads_or_edits_foreign_record_or_accepts_client_owner(owners):
    client, products, tokens, _, profiles = owners
    created = create(owners)
    path = f"{OWN}/{created['id']}"
    assert client.get(path, headers=tokens[1]).status_code == 404
    assert (
        client.patch(
            path, headers=tokens[1], json={"expected_version": 1, "title": "Foreign"}
        ).status_code
        == 404
    )
    assert (
        client.post(OWN, headers=tokens[0], json=body(products, partner_id=profiles[1])).status_code
        == 422
    )
    assert (
        client.patch(
            path, headers=tokens[0], json={"expected_version": 1, "partner_id": profiles[1]}
        ).status_code
        == 422
    )
    assert client.get(path, headers=tokens[0]).json() == created


def test_guest_and_ordinary_customer_cannot_use_owner_commands(owners):
    client, products, tokens, users, _ = owners
    created = create(owners)
    path = f"{OWN}/{created['id']}"
    assert client.get(OWN).status_code == 401
    assert client.get(path).status_code == 401
    assert client.post(OWN, json=body(products)).status_code == 401
    assert (
        client.patch(path, json={"expected_version": 1, "status": "published"}).status_code == 401
    )

    async def revoke():
        async with client.app.state.database.session() as session:
            await session.execute(delete(UserRole).where(UserRole.user_id == users[1]))
            await session.commit()

    client.portal.call(revoke)
    assert client.get(OWN, headers=tokens[1]).status_code == 403
    assert client.post(OWN, headers=tokens[1], json=body(products)).status_code == 403
    assert (
        client.patch(
            path, headers=tokens[1], json={"expected_version": 1, "title": "No"}
        ).status_code
        == 403
    )


def test_publish_rechecks_collection_and_status_only_withdrawal_still_works(owners):
    client, products, tokens, _, _ = owners
    created = create(owners)
    path = f"{OWN}/{created['id']}"
    published = client.patch(
        path, headers=tokens[0], json={"expected_version": 1, "status": "published"}
    )
    assert published.status_code == 200
    assert published.json()["version"] == 2
    assert published.json()["published_at"] is not None
    public = client.get(f"{PUBLIC}/{created['slug']}")
    assert public.status_code == 200
    assert public.json()["product_ids"] == [products[1], products[0]]
    assert "partner_id" not in public.json()

    async def withdraw_product():
        async with client.app.state.database.session() as session:
            await session.execute(
                update(Product).where(Product.id == products[0]).values(is_active=False)
            )
            await session.commit()

    client.portal.call(withdraw_product)
    hidden = client.patch(path, headers=tokens[0], json={"expected_version": 2, "status": "draft"})
    assert hidden.status_code == 200
    assert hidden.json()["version"] == 3
    assert hidden.json()["published_at"] is None
    assert client.get(f"{PUBLIC}/{created['slug']}").status_code == 404
    refused = client.patch(
        path, headers=tokens[0], json={"expected_version": 3, "status": "published"}
    )
    assert refused.status_code == 422
    assert refused.json()["detail"]["product_ids"] == [products[0]]
    assert client.get(path, headers=tokens[0]).json() == hidden.json()
    repaired = client.patch(
        path,
        headers=tokens[0],
        json={"expected_version": 3, "product_ids": [products[1]], "status": "published"},
    )
    assert repaired.status_code == 200
    assert repaired.json()["version"] == 4


@pytest.mark.parametrize("index", [3, 4, 5, None])
def test_owner_cannot_select_hidden_demo_hidden_category_or_missing_products(owners, index):
    client, products, tokens, _, _ = owners
    forbidden = products[index] if index is not None else 2_147_483_647
    response = client.post(OWN, headers=tokens[0], json=body(products, product_ids=[forbidden]))
    assert response.status_code == 422
    assert response.json()["detail"]["product_ids"] == [forbidden]
    created = create(owners)
    path = f"{OWN}/{created['id']}"
    response = client.patch(
        path,
        headers=tokens[0],
        json={
            "expected_version": 1,
            "title": "Must roll back",
            "product_ids": [products[0], forbidden],
        },
    )
    assert response.status_code == 422
    assert client.get(path, headers=tokens[0]).json() == created


def test_empty_draft_can_be_saved_but_cannot_be_published(owners):
    client, _, tokens, _, _ = owners
    created = create(owners, product_ids=[])
    path = f"{OWN}/{created['id']}"
    assert (
        client.patch(
            path, headers=tokens[0], json={"expected_version": 1, "status": "published"}
        ).status_code
        == 422
    )
    assert client.get(path, headers=tokens[0]).json() == created


def test_revocable_public_landing_is_never_stored_in_browser_or_shared_cache(owners):
    client, _, tokens, _, _ = owners
    created = create(owners, status="published")
    public = client.get(f"{PUBLIC}/{created['slug']}")
    assert public.status_code == 200
    assert public.headers["Cache-Control"] == "no-store"
    assert (
        client.patch(
            f"{OWN}/{created['id']}",
            headers=tokens[0],
            json={"expected_version": 1, "status": "draft"},
        ).status_code
        == 200
    )
    hidden = client.get(f"{PUBLIC}/{created['slug']}")
    assert hidden.status_code == 404
    assert hidden.headers["Cache-Control"] == "no-store"


def test_stale_version_never_changes_text_publication_or_product_links(owners):
    client, products, tokens, _, _ = owners
    created = create(owners)
    path = f"{OWN}/{created['id']}"
    saved = client.patch(
        path,
        headers=tokens[0],
        json={"expected_version": 1, "title": "Current", "product_ids": [products[2], products[0]]},
    )
    assert saved.status_code == 200
    assert saved.json()["version"] == 2
    for payload in (
        {"title": "Stale", "product_ids": [products[1]], "status": "published"},
        {"status": "archived"},
    ):
        stale = client.patch(path, headers=tokens[0], json={"expected_version": 1, **payload})
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "landing_version_conflict"
    assert client.get(path, headers=tokens[0]).json() == saved.json()


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"expected_version": 0},
        {"expected_version": True},
        {"expected_version": 1, "title": "   "},
        {"expected_version": 1, "content": {"faq": [{"question": " ", "answer": "Answer"}]}},
    ],
)
def test_updates_require_real_version_and_nonblank_normalized_text(owners, changes):
    client, _, tokens, _, _ = owners
    created = create(owners)
    path = f"{OWN}/{created['id']}"
    assert client.patch(path, headers=tokens[0], json=changes).status_code == 422
    assert client.get(path, headers=tokens[0]).json() == created


@pytest.mark.parametrize("status", ["invited", "suspended"])
def test_nonactive_partner_has_no_owner_editor_access(owners, status):
    client, products, tokens, _, profiles = owners
    created = create(owners)

    async def deactivate():
        async with client.app.state.database.session() as session:
            await session.execute(
                update(PartnerProfile).where(PartnerProfile.id == profiles[0]).values(status=status)
            )
            await session.commit()

    client.portal.call(deactivate)
    assert client.get(OWN, headers=tokens[0]).status_code == 404
    assert client.post(OWN, headers=tokens[0], json=body(products)).status_code == 404
    assert (
        client.patch(
            f"{OWN}/{created['id']}",
            headers=tokens[0],
            json={"expected_version": 1, "status": "published"},
        ).status_code
        == 404
    )


def test_owner_list_is_bounded_keyset_and_cursor_scoped_to_owner(owners):
    client, _, tokens, _, _ = owners
    rows = [create(owners) for _ in range(4)]
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT") and "FROM partner_landings" in statement:
            statements.append(statement)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        first = client.get(OWN, headers=tokens[0], params={"limit": 2})
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert first.status_code == 200
    assert first.headers["Cache-Control"] == "no-store"
    assert [row["id"] for row in first.json()["items"]] == [rows[3]["id"], rows[2]["id"]]
    assert len(statements) == 1
    assert "LIMIT" in statements[0].upper()
    cursor = first.json()["next_cursor"]
    assert cursor
    second = client.get(OWN, headers=tokens[0], params={"limit": 2, "cursor": cursor})
    assert [row["id"] for row in second.json()["items"]] == [rows[1]["id"], rows[0]["id"]]
    assert second.json()["next_cursor"] is None
    assert client.get(OWN, headers=tokens[1], params={"cursor": cursor}).status_code == 422
    assert client.get(OWN, headers=tokens[0], params={"limit": 25}).status_code == 422
    assert client.get(OWN, headers=tokens[0], params={"cursor": "broken"}).status_code == 422


def test_slug_collision_is_409_and_does_not_create_second_record(owners):
    client, products, tokens, _, _ = owners
    created = create(owners)
    duplicate = client.post(OWN, headers=tokens[1], json=body(products, slug=created["slug"]))
    assert duplicate.status_code == 409
    assert client.get(OWN, headers=tokens[1]).json()["items"] == []


def test_parallel_owner_and_admin_writers_commit_only_one_current_version(postgres_owners):
    client, products, tokens, users, _ = postgres_owners
    created = create(postgres_owners)

    async def admin_role():
        async with client.app.state.database.session() as session:
            role = await IdentityRepository().get_role(session, RoleName.ADMIN)
            session.add(UserRole(user_id=users[1], role_id=role.id))
            await session.commit()

    client.portal.call(admin_role)
    endpoints = [f"{OWN}/{created['id']}", f"/api/admin/partners/landings/{created['id']}"]
    barrier = Barrier(2)

    def write(index):
        barrier.wait(timeout=10)
        return client.patch(
            endpoints[index],
            headers=tokens[index],
            json={
                "expected_version": 1,
                "title": ["Owner edit", "Admin edit"][index],
                "product_ids": [[products[0]], [products[1]]][index],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(write, [0, 1]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert winner["version"] == 2
    assert client.get(endpoints[0], headers=tokens[0]).json() == winner


@pytest.mark.parametrize("change", ["version", "partner_status", "user_status"])
def test_write_rechecks_fresh_state_even_if_session_already_loaded_it(postgres_owners, change):
    client, products, tokens, users, profiles = postgres_owners
    created = create(postgres_owners)

    async def scenario():
        database = client.app.state.database
        service = client.app.state.partner_program_service
        async with database.session() as stale:
            await stale.get(User, users[0])
            await stale.get(PartnerProfile, profiles[0])
            loaded = await service.repository.get_landing(stale, landing_id=created["id"])
            assert loaded.version == 1
            async with database.session() as other:
                if change == "version":
                    await service.update_landing(
                        other,
                        owner_user_id=users[0],
                        landing_id=created["id"],
                        payload=PartnerLandingUpdateRequest(
                            expected_version=1, title="Newer edit", product_ids=[products[2]]
                        ),
                    )
                elif change == "partner_status":
                    await other.execute(
                        update(PartnerProfile)
                        .where(PartnerProfile.id == profiles[0])
                        .values(status="suspended")
                    )
                else:
                    await other.execute(
                        update(User).where(User.id == users[0]).values(status="blocked")
                    )
                await other.commit()
            error = (
                PartnerLandingVersionConflictError if change == "version" else PartnerNotFoundError
            )
            with pytest.raises(error):
                await service.update_landing(
                    stale,
                    owner_user_id=users[0],
                    landing_id=created["id"],
                    payload=PartnerLandingUpdateRequest(
                        expected_version=1, title="Stale overwrite", product_ids=[products[0]]
                    ),
                )
            await stale.rollback()
            fresh = await service.repository.get_landing(stale, landing_id=created["id"])
            assert fresh.title == ("Newer edit" if change == "version" else created["title"])
            assert fresh.version == (2 if change == "version" else 1)
            assert fresh.product_ids == (
                [products[2]] if change == "version" else created["product_ids"]
            )

    client.portal.call(scenario)


def test_admin_landing_directory_requires_manage_and_returns_bounded_summaries(owners):
    client, products, tokens, users, profiles = owners
    path = "/api/admin/partners/landings"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=tokens[0]).status_code == 403

    async def seed_directory():
        async with client.app.state.database.session() as session:
            role = await IdentityRepository().get_role(session, RoleName.ADMIN)
            session.add(UserRole(user_id=users[1], role_id=role.id))
            await session.commit()

    client.portal.call(seed_directory)
    for index in range(3):
        create(owners, title=f"Directory {index}")
    page = client.get(path, headers=tokens[1], params={"limit": 1})
    assert page.status_code == 200, page.text
    assert page.headers["cache-control"] == "no-store"
    row = page.json()["items"][0]
    assert row["product_count"] == 2 and row["version"] == 1
    assert not {"content", "product_ids", "description"} & row.keys()
    assert len(page.json()["items"]) == 1 and page.json()["next_cursor"]
    cursor = page.json()["next_cursor"]
    next_page = client.get(path, headers=tokens[1], params={"limit": 1, "cursor": cursor})
    assert next_page.status_code == 200 and next_page.json()["items"][0]["id"] < row["id"]
    for params in [{"limit": 101}, {"limit": 0}, {"status": "unknown"}, {"ignored": "no"}]:
        assert client.get(path, headers=tokens[1], params=params).status_code == 422
    changed = client.get(path, headers=tokens[1], params={"query": "changed", "cursor": cursor})
    assert changed.status_code == 422 and changed.json()["detail"]["code"] == "invalid_cursor"
    found = client.get(path, headers=tokens[1], params={"query": "directory 2"})
    assert len(found.json()["items"]) == 1
