from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.carts.router import router


@contextmanager
def cart_client(tmp_path):
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{tmp_path / (uuid4().hex + '.db')}",
    )
    database = DatabaseManager(settings)

    async def seed():
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(seed())

    @asynccontextmanager
    async def lifespan(_):
        try:
            yield
        finally:
            await database.shutdown()

    app = FastAPI(lifespan=lifespan)
    app.state.settings, app.state.database = settings, database
    app.include_router(router)
    with TestClient(app) as client:
        yield client


def write(revision=None, *, quantity=1, operation=None):
    return {
        "expected_revision": revision,
        "operation_id": operation or uuid4().hex,
        "items": [
            {
                "id": "one",
                "product_id": 7,
                "title": "Fixture",
                "price": "1000.00",
                "quantity": quantity,
            }
        ],
    }


def test_cart_requires_revision_and_replays_only_the_exact_same_operation(tmp_path):
    with cart_client(tmp_path) as client:
        empty = client.get("/api/cart/revision-fixture")
        assert empty.json()["revision"] is None
        assert empty.headers["cache-control"] == "no-store"
        request = write()
        saved = client.put("/api/cart/revision-fixture", json=request)
        assert saved.status_code == 200
        revision = saved.json()["revision"]
        assert len(revision) == 32
        assert saved.json()["items"][0]["quantity"] == 1
        assert client.put("/api/cart/revision-fixture", json=request).json() == saved.json()
        reused = client.put("/api/cart/revision-fixture", json={**request, "items": []})
        assert reused.status_code == 409
        assert reused.json()["detail"]["code"] == "cart_conflict"
        stale = client.put("/api/cart/revision-fixture", json=write())
        assert stale.status_code == 409
        assert stale.headers["cache-control"] == "no-store"
        assert client.get("/api/cart/revision-fixture").json()["revision"] == revision
        assert (
            client.put(
                "/api/cart/revision-fixture", json={"items": [], "updated_at_ms": 9_000_000_000_000}
            ).status_code
            == 422
        )
        assert client.delete("/api/cart/revision-fixture").status_code == 405


def test_empty_cart_has_a_revision_and_stale_writes_cannot_resurrect_items(tmp_path):
    with cart_client(tmp_path) as client:
        first = client.put("/api/cart/revision-fixture", json=write()).json()
        clear = {**write(first.get("revision")), "items": []}
        cleared = client.put("/api/cart/revision-fixture", json=clear)
        assert cleared.status_code == 200
        stale = client.put(
            "/api/cart/revision-fixture", json=write(first.get("revision"), quantity=2)
        )
        assert stale.status_code == 409
        current = client.get("/api/cart/revision-fixture").json()
        assert current["items"] == []
        assert current["revision"] == cleared.json()["revision"]


def test_replay_after_another_operation_conflicts_instead_of_rolling_back_the_cart(tmp_path):
    with cart_client(tmp_path) as client:
        original = write()
        first = client.put("/api/cart/revision-fixture", json=original).json()
        newer = client.put(
            "/api/cart/revision-fixture", json=write(first["revision"], quantity=4)
        ).json()
        assert client.put("/api/cart/revision-fixture", json=original).status_code == 409
        assert client.get("/api/cart/revision-fixture").json() == newer
