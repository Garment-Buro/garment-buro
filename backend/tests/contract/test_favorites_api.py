from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.db.session import DatabaseManager
from app.factory import create_app
from app.modules.catalog.models import Product
from tests.favorites_scenario import favorite_settings, seed_favorites

FAVORITES = "/api/profile/favorites"


@pytest.fixture
def favorites_setup(tmp_path: Path):
    settings = favorite_settings(f"sqlite+aiosqlite:///{tmp_path / 'favorites.db'}")
    products, tokens, users = asyncio.run(seed_favorites(settings))
    return settings, products, tokens, users


def test_favorites_persist_across_clients_and_restart_without_cross_account_access(favorites_setup):
    settings, products, (owner, other), _ = favorites_setup
    with TestClient(create_app(settings=settings)) as first:
        assert first.put(f"{FAVORITES}/{products[0]}", headers=owner).status_code == 204
        with TestClient(create_app(settings=settings)) as second:
            saved = second.get(FAVORITES, headers=owner)
            assert saved.status_code == 200
            assert saved.headers["cache-control"] == "no-store"
            assert [item["product_id"] for item in saved.json()["items"]] == [products[0]]
            assert saved.json()["items"][0]["saved_at"].endswith("Z")
            assert second.get(FAVORITES, headers=other).json()["items"] == []
            assert second.delete(f"{FAVORITES}/{products[0]}", headers=other).status_code == 204
    with TestClient(create_app(settings=settings)) as restarted:
        assert (
            restarted.get(FAVORITES, headers=owner).json()["items"][0]["product_id"] == products[0]
        )
        assert restarted.get(FAVORITES, headers=other).json()["items"] == []


def test_favorites_pagination_and_repeated_writes_are_stable(favorites_setup):
    settings, products, (owner, _), _ = favorites_setup
    with TestClient(create_app(settings=settings)) as client:
        for product in products[:3]:
            assert client.put(f"{FAVORITES}/{product}", headers=owner).status_code == 204
        assert client.put(f"{FAVORITES}/{products[1]}", headers=owner).status_code == 204
        first = client.get(FAVORITES, params={"limit": 2}, headers=owner).json()
        assert [item["product_id"] for item in first["items"]] == [products[2], products[1]]
        assert first["next_cursor"] is not None
        second = client.get(
            FAVORITES, params={"limit": 2, "cursor": first["next_cursor"]}, headers=owner
        ).json()
        assert [item["product_id"] for item in second["items"]] == [products[0]]
        assert second["next_cursor"] is None
        for _ in range(2):
            assert client.delete(f"{FAVORITES}/{products[1]}", headers=owner).status_code == 204
        remaining = client.get(FAVORITES, headers=owner).json()
        assert [item["product_id"] for item in remaining["items"]] == [products[2], products[0]]


def test_favorites_require_session_real_product_and_bounded_pagination(favorites_setup):
    settings, products, (owner, _), _ = favorites_setup
    with TestClient(create_app(settings=settings)) as client:
        assert client.get(FAVORITES).status_code == 401
        assert client.put(f"{FAVORITES}/{products[0]}").status_code == 401
        assert client.delete(f"{FAVORITES}/{products[0]}").status_code == 401
        assert client.get(FAVORITES, headers={"Authorization": "Bearer invalid"}).status_code == 401
        for product in [*products[3:], 99999]:
            assert client.put(f"{FAVORITES}/{product}", headers=owner).status_code == 404
        for invalid in (0, -1, 2**31, "preview-hoodie", "NaN"):
            assert client.put(f"{FAVORITES}/{invalid}", headers=owner).status_code == 422
            assert client.delete(f"{FAVORITES}/{invalid}", headers=owner).status_code == 422
        for params in (
            {"limit": 0},
            {"limit": 101},
            {"cursor": -1},
            {"cursor": 2**31},
            {"cursor": "NaN"},
        ):
            assert client.get(FAVORITES, params=params, headers=owner).status_code == 422
        assert client.get(FAVORITES, headers=owner).json() == {"items": [], "next_cursor": None}


def test_unpublished_favorites_are_hidden_and_can_still_be_removed(favorites_setup):
    settings, products, (owner, _), _ = favorites_setup

    async def hide():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                await session.execute(
                    update(Product).where(Product.id == products[0]).values(is_active=False)
                )
                await session.commit()
        finally:
            await database.shutdown()

    with TestClient(create_app(settings=settings)) as client:
        assert client.put(f"{FAVORITES}/{products[0]}", headers=owner).status_code == 204
        asyncio.run(hide())
        assert client.get(FAVORITES, headers=owner).json()["items"] == []
        assert client.delete(f"{FAVORITES}/{products[0]}", headers=owner).status_code == 204
