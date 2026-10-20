import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import select, update

from app.core.config import Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.checkout.contact import CheckoutContact
from app.modules.delivery.directory import (
    DIRECTORY_KEY,
    DirectoryTransport,
    PickupDirectory,
    normalize_points,
    search_statement,
)
from app.modules.delivery.directory_models import PickupDirectoryState, PickupPoint
from app.modules.delivery.directory_router import list_pickup_points
from app.modules.identity.repository import IdentityRepository


def point(code="TVR1", address="Советская, 12"):
    return {
        "code": code,
        "work_time": "10:00–20:00",
        "location": {
            "city": "Тверь",
            "address": address,
            "latitude": 56.8,
            "longitude": 35.9,
        },
    }


async def database_at(path):
    database = DatabaseManager(
        Settings(
            _env_file=None,
            app_env="test",
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{path}",
        )
    )
    await database.startup()
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        session.add(PickupDirectoryState(key=DIRECTORY_KEY))
        await IdentityRepository().ensure_system_authorization(session)
        await session.commit()
    return database


def test_directory_atomic_refresh_ttl_search_and_outage(tmp_path, monkeypatch):
    calls = []

    async def fetch(_):
        calls.append(1)
        return [point(), point("TVR2", "Берёзовая, 2")]

    monkeypatch.setattr(DirectoryTransport, "fetch_points", fetch)

    async def scenario():
        database = await database_at(tmp_path / "points.db")
        directory = PickupDirectory(database, database.settings)
        try:
            assert await directory.refresh()
            assert not await directory.refresh()
            assert len(calls) == 1
            async with database.session() as session:
                found = list(await session.scalars(search_statement("ТВЕРЬ березовая")))
                assert [value.code for value in found] == ["TVR2"]
                assert not list(await session.scalars(search_statement("%_")))
                page = await list_pickup_points(Response(), session, q="Тверь", limit=1)
                assert page["total"] == 2 and len(page["points"]) == 1
                await session.execute(
                    update(PickupDirectoryState).values(
                        updated_at=datetime.now(UTC) - timedelta(days=2)
                    )
                )
                await session.commit()

            async def invalid(_):
                return []

            monkeypatch.setattr(DirectoryTransport, "fetch_points", invalid)
            with pytest.raises(ValueError):
                await directory.refresh()
            assert not await directory.refresh()  # failure backoff persists in database
            async with database.session() as session:
                assert len(list(await session.scalars(select(PickupPoint)))) == 2
                page = await list_pickup_points(Response(), session)
                assert page["stale"] is True
                await session.execute(
                    update(PickupDirectoryState).values(
                        updated_at=datetime.now(UTC) - timedelta(days=8)
                    )
                )
                await session.commit()
                with pytest.raises(HTTPException) as caught:
                    await list_pickup_points(Response(), session)
                assert caught.value.status_code == 503
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_empty_directory_is_unavailable_not_demo(tmp_path):
    async def scenario():
        database = await database_at(tmp_path / "empty.db")
        try:
            async with database.session() as session:
                with pytest.raises(HTTPException) as caught:
                    await list_pickup_points(Response(), session)
                assert caught.value.status_code == 503
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_contacts_and_directory_reject_invalid_values():
    valid = {
        "name": "  Анна   Соколова  ",
        "phone": "+7 (900) 123-45-67",
        "email": "Anna@example.test",
    }
    contact = CheckoutContact(**valid)
    assert contact.name == "Анна Соколова"
    assert contact.phone == "+79001234567"
    assert contact.email == "anna@example.test"
    for invalid in ({"name": " "}, {"phone": "abc"}, {"email": "not-an-email"}):
        with pytest.raises(ValidationError):
            CheckoutContact(**(valid | invalid))
    for raw in ([], {}, [{"code": "x"}]):
        with pytest.raises(ValueError):
            normalize_points(raw)
