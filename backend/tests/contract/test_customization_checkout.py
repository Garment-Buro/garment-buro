from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app.modules.orders.security import generate_order_guest_access_token
from tests.contract.test_checkout_api import CheckoutProvider, _application, _command, _headers


def test_custom_prints_are_charged_and_replayed_without_another_payment(tmp_path: Path) -> None:
    provider = CheckoutProvider()
    application, _, product_id, proof = _application(tmp_path, provider)
    token = generate_order_guest_access_token()
    command = _command(product_id, quote=proof, claimed_total_price="650.50")
    command["items"][0]["customization"] = {
        "kind": "constructor",
        "totalPrice": 1,
        "comment": "Keep this design",
        "decorations": [
            {"uid": "print", "scale": 1.5, "price": 0, "view": "front", "image": "/print.webp"},
            {"uid": "text", "scale": 0.25, "price": 0, "view": "back", "text": {"content": "Hi"}},
        ],
    }
    with TestClient(application) as client:
        underpriced = deepcopy(command)
        underpriced["claimed_total_price"] = "250.50"
        rejected = client.post(
            "/api/orders",
            json=underpriced,
            headers=_headers(guest_token=token, key="custom_price_underclaimed"),
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"] == {
            "code": "checkout_price_changed",
            "currency": "RUB",
            "prices": [{"id": "checkout-line-1", "product_id": product_id, "price": 300.25}],
        }
        assert provider.calls == []
        response = client.post("/api/orders", json=command, headers=_headers(guest_token=token))
        assert response.status_code == 200, response.json()
        replay = client.post("/api/orders", json=command, headers=_headers(guest_token=token))
        assert replay.status_code == 200
        assert replay.json()["order_id"] == response.json()["order_id"]
        stored = client.get("/api/order-access", headers={"X-Order-Access-Token": token}).json()
        assert stored["total_price"] == 650.50
        line = json.loads(stored["cart_items"])[0]
        assert line["price"] == 300.25
        assert line["customization"]["totalPrice"] == 300.25
        assert [d["price"] for d in line["customization"]["decorations"]] == [120, 80]
        assert line["customization"]["comment"] == "Keep this design"
    assert len(provider.calls) == 1
