"""Real HTTP checkout transactions; local synthetic payment and storage adapters."""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.carts.models import Cart
from app.modules.catalog.models import Product, ProductVariant
from app.modules.design_assets.models import CartDesignAsset, DesignAsset, OrderDesignAsset
from app.modules.identity.security import ensure_utc
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import Order
from app.modules.orders.security import generate_order_guest_access_token
from app.modules.payments.models import PaymentAttempt
from tests.contract.test_checkout_api import (
    CheckoutProvider,
    _application,
    _command,
    _headers,
    _settings,
)
from tests.contract.test_design_media_api import image_bytes
from tests.contract.test_public_profile_media import AvatarClient


async def state(settings, *, expire=False, stock=None):
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            if expire:
                await session.execute(
                    update(DesignAsset).values(
                        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
                    )
                )
            if stock is not None:
                await session.execute(update(Product).values(stock_quantity=stock))
                await session.execute(update(ProductVariant).values(stock_quantity=stock))
            if expire or stock is not None:
                await session.commit()
            return {
                "assets": [
                    (row.id, row.expires_at) for row in await session.scalars(select(DesignAsset))
                ],
                "cart_links": (
                    await session.execute(
                        select(CartDesignAsset.cart_id, CartDesignAsset.design_asset_id)
                    )
                ).all(),
                "order_links": (
                    await session.execute(
                        select(OrderDesignAsset.order_id, OrderDesignAsset.design_asset_id)
                    )
                ).all(),
                "cart_expiries": list(await session.scalars(select(Cart.expires_at))),
                "orders": await session.scalar(select(func.count()).select_from(Order)),
                "payments": await session.scalar(select(func.count()).select_from(PaymentAttempt)),
                "reservations": await session.scalar(
                    select(func.count()).select_from(InventoryReservation)
                ),
            }
    finally:
        await database.shutdown()


def application(tmp_path, provider, *, settings=None):
    base = settings or _settings(tmp_path / "checkout.db")
    return _application(
        tmp_path, provider, settings=base.model_copy(update={"carts_v2_enabled": True})
    )


def command_with_image(product_id, quote, path):
    command = _command(product_id, quote=quote, claimed_total_price="410.50")
    command["items"][0].update(
        image=path,
        customization={
            "kind": "constructor",
            "modelImages": {"front": path, "back": path},
            "decorations": [{"uid": "print", "scale": 1, "image": path, "view": "front"}],
        },
    )
    return command


def exercise_retention(tmp_path, *, settings=None, sdk=None, outcome="success"):
    provider = CheckoutProvider(outcomes=[outcome])
    app, _, product_id, quote = application(tmp_path, provider, settings=settings)
    settings = app.state.settings
    sdk = sdk or AvatarClient()
    with TestClient(app) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk)
        uploaded = client.post("/api/design-media", content=image_bytes())
        assert uploaded.status_code == 201, uploaded.text
        path = uploaded.json()["url"]
        command = command_with_image(product_id, quote, path)
        body = {"expected_revision": None, "operation_id": uuid4().hex, "items": command["items"]}
        cart_path = "/api/cart/design-checkout-fixture"
        saved = client.put(cart_path, json=body)
        assert saved.status_code == 200, saved.text
        assert saved.json()["items"][0]["price"] == 180.25
        before = asyncio.run(state(settings))
        assert len(before["cart_links"]) == 1
        assert ensure_utc(before["assets"][0][1]) >= ensure_utc(before["cart_expiries"][0])
        assert client.put(cart_path, json=body).json() == saved.json()
        assert asyncio.run(state(settings)) == before

        headers = _headers(guest_token=generate_order_guest_access_token())
        created = client.post("/api/orders", json=command, headers=headers)
        assert created.status_code == (200 if outcome == "success" else 503), created.text
        accepted = asyncio.run(state(settings))
        assert accepted["orders"] == accepted["payments"] == 1
        assert accepted["reservations"] == 1
        assert len(accepted["order_links"]) == 1
        assert accepted["assets"][0][1] is None
        order_id = (created.json() if outcome == "success" else created.json()["detail"])[
            "order_id"
        ]
        assert accepted["order_links"][0][0] == order_id
        if outcome == "success":
            replay = client.post("/api/orders", json=command, headers=headers)
            assert replay.status_code == 200, replay.text
            assert replay.json()["order_id"] == order_id
            assert asyncio.run(state(settings)) == accepted
        else:
            assert created.json()["detail"]["code"] == "payment_outcome_unknown"
        cleared = client.put(
            cart_path,
            json={
                "expected_revision": saved.json()["revision"],
                "operation_id": uuid4().hex,
                "items": [],
            },
        )
        assert cleared.status_code == 200
        after = asyncio.run(state(settings))
        assert after["cart_links"] == []
        assert after["order_links"] == accepted["order_links"]
        assert client.get(path).status_code == 200
    assert len(provider.calls) == 1
    if isinstance(sdk, AvatarClient):
        assert sdk.presigns == []
    return settings, path


def test_cart_and_checkout_atomically_retain_one_image_and_replay_without_duplicates(tmp_path):
    exercise_retention(tmp_path)


def test_unknown_payment_result_keeps_accepted_order_images(tmp_path):
    exercise_retention(tmp_path, outcome="timeout")


def exercise_rollback(tmp_path, *, settings=None, sdk=None):
    provider = CheckoutProvider()
    app, _, product_id, quote = application(tmp_path, provider, settings=settings)
    settings = app.state.settings
    with TestClient(app) as client:
        client.app.state.storage = MinioStorage(settings, client=sdk or AvatarClient())
        path = client.post("/api/design-media", content=image_bytes()).json()["url"]
        before = asyncio.run(state(settings, stock=1))
        rejected = client.post(
            "/api/orders",
            json=command_with_image(product_id, quote, path),
            headers=_headers(guest_token=generate_order_guest_access_token()),
        )
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["detail"]["code"] == "checkout_stock_unavailable"
        assert asyncio.run(state(settings)) == before
        assert before["assets"][0][1] is not None
        assert before["order_links"] == [] and before["orders"] == 0
        assert client.get(path).status_code == 200
    assert provider.calls == []


def test_stock_failure_after_order_file_attachment_rolls_back_order_links_and_expiry(tmp_path):
    exercise_rollback(tmp_path)


@pytest.mark.parametrize("expired", [False, True])
def test_missing_or_expired_image_rejects_cart_and_order_without_writes(tmp_path, expired):
    provider = CheckoutProvider()
    app, _, product_id, quote = application(tmp_path, provider)
    settings = app.state.settings
    with TestClient(app) as client:
        client.app.state.storage = MinioStorage(settings, client=AvatarClient())
        path = client.post("/api/design-media", content=image_bytes()).json()["url"]
        if expired:
            asyncio.run(state(settings, expire=True))
        else:
            path = path.replace(path.split("/")[-2], "z" * 43)
        cart_path = "/api/cart/design-invalid-fixture"
        first = client.put(
            cart_path, json={"expected_revision": None, "operation_id": uuid4().hex, "items": []}
        )
        assert first.status_code == 200
        before = asyncio.run(state(settings))
        command = command_with_image(product_id, quote, path)
        rejected = client.put(
            cart_path,
            json={
                "expected_revision": first.json()["revision"],
                "operation_id": uuid4().hex,
                "items": command["items"],
            },
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "cart_design_unavailable"
        assert rejected.headers["cache-control"] == "no-store"
        assert client.get(cart_path).json() == first.json()
        rejected = client.post(
            "/api/orders",
            json=deepcopy(command),
            headers=_headers(guest_token=generate_order_guest_access_token()),
        )
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["detail"]["code"] == "checkout_design_unavailable"
        assert asyncio.run(state(settings)) == before
    assert provider.calls == []
