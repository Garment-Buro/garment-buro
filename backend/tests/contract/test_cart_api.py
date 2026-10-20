from sqlalchemy import select

from app.modules.carts.models import Cart, CartItem
from app.modules.carts.security import digest_cart_id
from tests.contract.test_cart_revisions import cart_client, write


def test_persistent_cart_contract_validates_items_and_stores_only_token_digest(tmp_path):
    with cart_client(tmp_path) as client:
        request = write()
        request["items"][0]["customization"] = {"fit": {"lengthCm": 70}}
        first = client.put("/api/cart/guest-contract", json=request)
        assert first.status_code == 200
        assert first.json()["items"][0]["customization"] == {"fit": {"lengthCm": 70}}
        updated = client.put("/api/cart/guest-contract", json=write(first.json()["revision"]))
        assert updated.status_code == 200
        assert updated.json()["items"][0]["customization"] is None
        assert client.get("/api/cart/bad").status_code == 400
        duplicate = write(updated.json()["revision"])
        duplicate["items"] *= 2
        assert client.put("/api/cart/guest-contract", json=duplicate).status_code == 422
        assert (
            client.put(
                "/api/cart/guest-contract", json={**write(), "expected_revision": "bad"}
            ).status_code
            == 422
        )
        assert (
            client.put(
                "/api/cart/guest-contract", json={**write(), "operation_id": "bad"}
            ).status_code
            == 422
        )
        database = client.app.state.database

        async def verify_digest():
            async with database.session() as session:
                cart = await session.scalar(select(Cart))
                assert cart.token_digest_sha256 == digest_cart_id("guest-contract")
                assert "guest-contract" not in repr(cart.__dict__)
                assert await session.scalar(select(CartItem)) is not None

        client.portal.call(verify_digest)
        clear = {**write(updated.json()["revision"]), "items": []}
        assert client.put("/api/cart/guest-contract", json=clear).status_code == 200

        async def verify_empty():
            async with database.session() as session:
                assert await session.scalar(select(CartItem)) is None
                assert (await session.scalar(select(Cart))).revision is not None

        client.portal.call(verify_empty)
