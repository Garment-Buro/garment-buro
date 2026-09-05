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
from app.modules.checkout.customer import prepare_checkout_customer
from app.modules.checkout.legacy_contact import prepare_legacy_contact_order
from app.modules.delivery.directory import (
    DIRECTORY_KEY,
    DirectoryTransport,
    PickupDirectory,
    normalize_points,
    search_statement,
)
from app.modules.delivery.directory_models import PickupDirectoryState, PickupPoint
from app.modules.delivery.directory_router import list_pickup_points
from app.modules.identity.models import User
from app.modules.identity.repository import IdentityRepository


def point(code="TVR1", address="Советская, 12"):
    return {"code": code, "work_time": "10:00–20:00", "location": {
        "city": "Тверь", "address": address, "latitude": 56.8, "longitude": 35.9,
    }}


async def database_at(path):
    database = DatabaseManager(Settings(_env_file=None, app_env="test", database_enabled=True,
                                        database_url=f"sqlite+aiosqlite:///{path}"))
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
                await session.execute(update(PickupDirectoryState).values(
                    updated_at=datetime.now(UTC) - timedelta(days=2)))
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
                await session.execute(update(PickupDirectoryState).values(
                    updated_at=datetime.now(UTC) - timedelta(days=8)))
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


def test_checkout_customer_is_not_verified_or_overwritten(tmp_path):
    async def scenario():
        database = await database_at(tmp_path / "identity.db")
        try:
            await prepare_checkout_customer(database, " Anna@Example.test ")
            await prepare_checkout_customer(database, "anna@example.test")
            async with database.session() as session:
                users = list(await session.scalars(select(User)))
                assert len(users) == 1
                assert users[0].email_normalized == "anna@example.test"
                assert users[0].email_verified_at is None
                assert users[0].phone is None
                users[0].first_name = "Сохранённое имя"
                await session.commit()
            await prepare_checkout_customer(database, "ANNA@example.test")
            async with database.session() as session:
                user = await session.scalar(select(User))
                assert user.first_name == "Сохранённое имя"
        finally:
            await database.shutdown()
    asyncio.run(scenario())


def test_contacts_and_directory_reject_invalid_values():
    valid = {"name": "  Анна   Соколова  ", "phone": "+7 (900) 123-45-67", "email": "Anna@example.test"}
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


def test_recipient_does_not_own_buyer_order_and_address_is_canonical(tmp_path, monkeypatch):
    async def quote(city, method, items):
        assert city == "Тверь" and method == "cdek_pickup"
        return {"delivery_price": 450.0}
    monkeypatch.setattr("app.modules.checkout.legacy_contact.quote_legacy_delivery", quote)

    async def scenario():
        database = await database_at(tmp_path / "contacts.db")
        buyer = CheckoutContact(name="Анна Соколова", email="buyer@example.test", phone="+79001234567")
        recipient = CheckoutContact(name="Мария Соколова", email="recipient@example.test", phone="+79007654321")
        payload = {"delivery_city": "Подмена", "delivery_address": "Подмена", "delivery_method": "cdek_pickup",
                   "cdek_point_code": "TVR1", "cart_items": '[{"quantity":1}]', "delivery_price": 450.0}
        try:
            async with database.session() as session:
                session.add(PickupPoint(**normalize_points([point()])[0]))
                await session.execute(update(PickupDirectoryState).values(updated_at=datetime.now(UTC)))
                await session.commit()
            result = await prepare_legacy_contact_order(dict(payload), buyer=buyer, recipient=recipient, database=database)
            assert result["email"] == "buyer@example.test"
            assert result["phone"] == recipient.phone
            assert result["first_name"] == recipient.name
            assert result["recipient_email"] == recipient.email
            assert result["delivery_address"] == "Тверь, Советская, 12"
            async with database.session() as session:
                assert [u.email_normalized for u in await session.scalars(select(User))] == [buyer.email]
            with pytest.raises(HTTPException) as error:
                await prepare_legacy_contact_order(payload | {"cdek_point_code": "deleted"}, buyer=buyer, recipient=None, database=database)
            assert error.value.status_code == 422
            with pytest.raises(HTTPException) as error:
                await prepare_legacy_contact_order(payload | {"delivery_price": 0}, buyer=buyer, recipient=None, database=database)
            assert error.value.status_code == 409
        finally:
            await database.shutdown()
    asyncio.run(scenario())
