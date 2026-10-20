from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.modules.carts.router import router as cart_router
from tests.contract.test_checkout_api import CheckoutProvider, _application


def test_preview_is_public_small_read_and_cart_uses_identical_policy(tmp_path: Path) -> None:
    provider = CheckoutProvider()
    application, database, product_id, _ = _application(tmp_path, provider)
    application.include_router(cart_router)
    statements = []
    with TestClient(application) as client:
        event.listen(
            database.engine.sync_engine,
            "before_cursor_execute",
            lambda *args: statements.append(args[2]),
        )
        url = f"/api/catalog/products/{product_id}/price"
        design = {"decorations": [{"uid": "a", "scale": 1.5}, {"uid": "b", "scale": 0.25}]}
        preview = client.post(url, json=design)
        assert preview.status_code == 200
        assert preview.headers["cache-control"] == "no-store"
        quote = preview.json()
        assert quote["product_id"] == product_id
        assert Decimal(quote["decoration_base_price"]) == 80
        assert Decimal(quote["base_price"]) == Decimal("100.25")
        assert Decimal(quote["total_price"]) == Decimal("300.25")
        assert Decimal(quote["customization_price"]) == 200
        assert [Decimal(d["price"]) for d in quote["decorations"]] == [120, 80]
        assert len(statements) == 1
        assert statements[0].lstrip().upper().startswith("SELECT")
        assert (
            client.post(url, json={"decorations": [{"uid": "a", "scale": True}]}).status_code == 422
        )
        assert client.post(url, json={"decorations": [{"uid": "a", "scale": 0}]}).status_code == 422
        assert (
            client.post(url, json={"decorations": [{"uid": "a", "scale": 1}] * 2}).status_code
            == 422
        )
        for invalid in (0, -1, 2_147_483_648):
            assert (
                client.post(f"/api/catalog/products/{invalid}/price", json=design).status_code
                == 422
            )
        assert client.post("/api/catalog/products/2147483647/price", json=design).status_code == 404
        cart = {
            "expected_revision": None,
            "operation_id": uuid4().hex,
            "items": [
                {
                    "id": "custom",
                    "product_id": product_id,
                    "title": "Synthetic",
                    "price": 1,
                    "quantity": 1,
                    "size": "M",
                    "color": "black",
                    "customization": {"kind": "constructor", "totalPrice": 1, **design},
                }
            ],
        }
        cart["items"].append(
            {
                **cart["items"][0],
                "id": "second",
                "customization": {
                    "kind": "constructor",
                    "decorations": [{"uid": "c", "scale": 1}],
                },
            }
        )
        statements.clear()
        saved = client.put("/api/cart/pricing-preview", json=cart)
        assert saved.status_code == 200
        assert sum("FROM products" in statement for statement in statements) == 1
        restored_items = client.get("/api/cart/pricing-preview").json()["items"]
        restored = restored_items[0]
        assert restored["price"] == 300.25
        assert restored["customization"]["totalPrice"] == 300.25
        assert restored_items[1]["price"] == 180.25
        import sqlite3

        with sqlite3.connect(tmp_path / "target.db") as connection:
            connection.execute("UPDATE products SET price=200")
        statements.clear()
        replay = client.put("/api/cart/pricing-preview", json=cart)
        assert replay.json() == saved.json()
        assert not any("FROM products" in statement for statement in statements)
        cart["items"][0]["customization"]["decorations"][0]["scale"] = -1
        assert client.put("/api/cart/pricing-preview", json=cart).status_code == 422
        assert client.get("/api/cart/pricing-preview").json()["items"][0] == restored
    assert provider.calls == []


def test_withdrawn_or_demo_product_has_no_public_preview(tmp_path: Path) -> None:
    import sqlite3

    application, _, product_id, _ = _application(tmp_path, CheckoutProvider())
    with sqlite3.connect(tmp_path / "target.db") as connection:
        category_id = connection.execute(
            "INSERT INTO product_categories(slug,name,is_active) VALUES ('hidden','Hidden',0)"
        ).lastrowid
    with TestClient(application) as client:
        for mutation in (
            "is_active=0",
            "is_active=1, is_demo=1",
            f"is_active=1,is_demo=0,category_id={category_id}",
        ):
            with sqlite3.connect(tmp_path / "target.db") as connection:
                connection.execute(f"UPDATE products SET {mutation}")
            response = client.post(
                f"/api/catalog/products/{product_id}/price", json={"decorations": []}
            )
            assert response.status_code == 404
            assert response.headers["cache-control"] == "no-store"
