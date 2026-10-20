"""Customer history is bounded metadata; details keep accepted order snapshots."""

import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.db.session import DatabaseManager
from app.factory import create_app
from tests.contract.test_order_read_api import (
    _create_legacy_orders,
    _login,
    _seed_target,
    _settings,
)


def test_customer_history_pages_metadata_without_loading_order_documents(tmp_path):
    source = tmp_path / "legacy.db"
    carts = _create_legacy_orders(source)
    settings = _settings(tmp_path)
    _seed_target(settings, source)
    database = DatabaseManager(settings)
    app = create_app(settings=settings, database=database)
    with TestClient(app) as client:
        token, user_id = _login(client, tmp_path / "target.db", "customer@example.test")
        headers = {"Authorization": "Bearer " + token}
        with sqlite3.connect(tmp_path / "target.db") as connection:
            # An imported order may already have both a direct owner and a claim.
            connection.execute("UPDATE orders SET user_id=? WHERE id=10", (user_id,))
            connection.execute(
                "UPDATE legacy_order_imports SET delivery_provider_number='cdek-10' WHERE order_id=10"
            )
            connection.executemany(
                "INSERT INTO orders (id,user_id,items_subtotal,delivery_price,total_price,"
                "request_fingerprint_sha256) VALUES (?,?,100,0,100,?)",
                [(order_id, user_id, f"{order_id:064x}") for order_id in range(100, 130)]
                + [(order_id, None, f"{order_id:064x}") for order_id in range(500, 600)],
            )
            connection.commit()
        statements = []

        def capture(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.lower())

        event.listen(database.engine.sync_engine, "before_cursor_execute", capture)
        try:
            first = client.get("/api/auth/orders", headers=headers)
            assert first.status_code == 200
            assert first.headers["cache-control"] == "no-store"
            page = first.json()
            assert isinstance(page, dict), "History must return a bounded summary page"
            assert [row["id"] for row in page["items"]] == list(range(129, 105, -1))
            assert page["next_cursor"] == 106
            assert set(page["items"][0]) == {
                "id",
                "total_price",
                "created_at",
                "status",
                "payment_status",
                "customer_stage",
                "customer_stage_label",
                "cdek_number",
                "cdek_status",
            }
            assert all("order_items" not in query for query in statements)
            assert all("raw_cart_items" not in query for query in statements)
        finally:
            event.remove(database.engine.sync_engine, "before_cursor_execute", capture)
        with sqlite3.connect(tmp_path / "target.db") as connection:
            connection.execute(
                "INSERT INTO orders (id,user_id,items_subtotal,delivery_price,total_price,"
                "request_fingerprint_sha256) VALUES (2000,?,100,0,100,?)",
                (user_id, "f" * 64),
            )
            connection.commit()
        second = client.get("/api/auth/orders?cursor=106", headers=headers).json()
        assert [row["id"] for row in second["items"]] == [105, 104, 103, 102, 101, 100, 10]
        assert second["next_cursor"] is None
        assert second["items"][-1]["cdek_number"] == "cdek-10"
        assert client.get("/api/orders/10", headers=headers).json()["cart_items"] == carts[10]
        assert client.get("/api/orders/500", headers=headers).status_code == 404
        assert client.get("/api/auth/orders?cursor=10", headers=headers).json() == {
            "items": [],
            "next_cursor": None,
        }
        assert len(client.get("/api/auth/orders?limit=1", headers=headers).json()["items"]) == 1


def test_customer_history_rejects_unbounded_or_invalid_pages(tmp_path):
    settings = _settings(tmp_path)
    source = tmp_path / "legacy.db"
    _create_legacy_orders(source)
    _seed_target(settings, source)
    app = create_app(settings=settings, database=DatabaseManager(settings))
    with TestClient(app) as client:
        assert client.get("/api/auth/orders").status_code == 401
        token, _ = _login(client, tmp_path / "target.db", "unrelated@example.test")
        headers = {"Authorization": "Bearer " + token}
        for query in [
            "limit=0",
            "limit=101",
            "cursor=0",
            "cursor=-1",
            "cursor=1.5",
            "cursor=2147483648",
            "cursor=secret",
        ]:
            assert client.get("/api/auth/orders?" + query, headers=headers).status_code == 422
        assert client.get("/api/auth/orders?limit=100", headers=headers).json() == {
            "items": [],
            "next_cursor": None,
        }
