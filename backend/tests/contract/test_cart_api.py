from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.carts.models import Cart, CartItem
from app.modules.carts.router import router as cart_router


def test_persistent_cart_api_preserves_contract_and_conflict_order(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'cart-api.db'}",
    )
    database = DatabaseManager(settings)

    async def seed() -> None:
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(seed())

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            await database.shutdown()

    application = FastAPI(lifespan=lifespan)
    application.state.settings = settings
    application.state.database = database
    application.include_router(cart_router)

    newest = {
        "updated_at_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "items": [
            {
                "id": "1_M_black",
                "product_id": 1,
                "title": "Persistent product",
                "price": 1000,
                "image": "/uploads/item.webp",
                "size": "M",
                "color": "black",
                "quantity": 1,
                "customization": {"fit": {"lengthCm": 70}},
            }
        ],
    }
    with TestClient(application) as client:
        empty = client.get("/api/cart/guest-contract")
        assert empty.status_code == 200
        assert empty.json() == {
            "cart_id": "guest-contract",
            "items": [],
            "updated_at_ms": 0,
            "ttl_seconds": 2_592_000,
        }

        saved = client.put("/api/cart/guest-contract", json=newest)
        assert saved.status_code == 200
        assert saved.json() == {
            "status": "ok",
            "cart_id": "guest-contract",
            "items_count": 1,
            "updated_at_ms": newest["updated_at_ms"],
            "ttl_seconds": 2_592_000,
        }
        without_customization = {
            **newest,
            "updated_at_ms": newest["updated_at_ms"] + 1,
            "items": [
                {key: value for key, value in newest["items"][0].items() if key != "customization"}
            ],
        }
        assert client.put("/api/cart/guest-contract", json=without_customization).status_code == 200
        legacy_shape = client.get("/api/cart/guest-contract").json()["items"][0]
        assert "customization" not in legacy_shape

        newest["updated_at_ms"] += 2
        assert client.put("/api/cart/guest-contract", json=newest).status_code == 200
        stale = client.put(
            "/api/cart/guest-contract",
            json={"items": [], "updated_at_ms": newest["updated_at_ms"] - 1},
        )
        assert stale.status_code == 200
        assert stale.json()["items_count"] == 1
        restored = client.get("/api/cart/guest-contract")
        assert restored.json()["items"][0]["customization"] == {"fit": {"lengthCm": 70}}

        assert client.get("/api/cart/bad").status_code == 400
        duplicate = {**newest, "items": [newest["items"][0], newest["items"][0]]}
        assert client.put("/api/cart/guest-contract", json=duplicate).status_code == 422
        future = {
            "items": [],
            "updated_at_ms": newest["updated_at_ms"] + 3600 * 1000,
        }
        assert client.put("/api/cart/guest-contract", json=future).status_code == 422
        deleted = client.delete("/api/cart/guest-contract")
        assert deleted.status_code == 200
        assert deleted.json() == {"status": "deleted", "cart_id": "guest-contract"}
        assert client.get("/api/cart/guest-contract").json()["items"] == []

    async def verify_no_raw_token() -> None:
        await database.startup()
        async with database.session() as session:
            assert await session.scalar(select(Cart)) is None
            assert await session.scalar(select(CartItem)) is None
        await database.shutdown()

    asyncio.run(verify_no_raw_token())
