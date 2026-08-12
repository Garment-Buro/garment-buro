from __future__ import annotations

import importlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def legacy_app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[FastAPI]:
    backend_dir = Path(__file__).resolve().parents[2]
    runtime_dir = tmp_path_factory.mktemp("legacy-backend")
    environment = pytest.MonkeyPatch()

    try:
        # The legacy app resolves SQLite and uploads relative to the process CWD.
        # Keeping them in a temporary directory makes the characterization tests
        # deterministic and prevents them from touching a developer database.
        environment.chdir(runtime_dir)
        environment.syspath_prepend(str(backend_dir))
        environment.setenv("APP_ENV", "test")
        environment.setenv("REDIS_URL", "")
        environment.setenv("JWT_SECRET", "contract-test-jwt-secret")
        environment.setenv("CDEK_CLIENT_ID", "contract-test")
        environment.setenv("CDEK_CLIENT_SECRET", "contract-test")
        environment.setenv("YOOKASSA_SHOP_ID", "contract-test")
        environment.setenv("YOOKASSA_API_KEY", "contract-test")
        environment.setenv("SMTP_PASSWORD", "contract-test")

        from app.core.config import get_settings

        get_settings.cache_clear()

        legacy_main = importlib.import_module("main")
        yield legacy_main.app
    finally:
        from app.core.config import get_settings

        get_settings.cache_clear()
        environment.undo()


@pytest.fixture()
def client(legacy_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(legacy_app) as test_client:
        yield test_client


def test_frontend_routes_are_registered(legacy_app: FastAPI) -> None:
    registered = {
        (method, route.path)
        for route in legacy_app.routes
        for method in getattr(route, "methods", set())
    }

    expected = {
        ("GET", "/api/products"),
        ("GET", "/api/products/{product_id}"),
        ("POST", "/api/products"),
        ("PUT", "/api/products/{product_id}"),
        ("DELETE", "/api/products/{product_id}"),
        ("GET", "/api/cart/{cart_id}"),
        ("PUT", "/api/cart/{cart_id}"),
        ("POST", "/api/auth/email/request"),
        ("POST", "/api/auth/email/verify"),
        ("GET", "/api/auth/me"),
        ("GET", "/api/auth/orders"),
        ("POST", "/api/orders"),
        ("GET", "/api/orders"),
        ("GET", "/api/orders/{order_id}"),
        ("POST", "/api/upload"),
        ("GET", "/api/options"),
        ("PUT", "/api/options"),
        ("GET", "/api/settings"),
        ("PUT", "/api/settings"),
        ("POST", "/api/cdek/calculate"),
        ("POST", "/api/webhooks/yookassa"),
    }

    assert expected <= registered


def test_catalog_response_keeps_frontend_fields(client: TestClient) -> None:
    response = client.get("/api/products")

    assert response.status_code == 200
    products = response.json()
    assert len(products) == 4
    assert {
        "id",
        "title",
        "price",
        "old_price",
        "is_active",
        "stock_quantity",
        "desktop_slider_images",
        "mobile_card_image",
    } <= products[0].keys()

    detail_response = client.get(f"/api/products/{products[0]['id']}")
    assert detail_response.status_code == 200
    assert "variants" in detail_response.json()


def test_default_options_and_settings_keep_frontend_shape(client: TestClient) -> None:
    options_response = client.get("/api/options")
    settings_response = client.get("/api/settings")

    assert options_response.status_code == 200
    assert options_response.json() == {
        "colors": [
            {"label": "Черный", "hex": "#1A1A1A"},
            {"label": "Белый", "hex": "#FFFFFF"},
        ],
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
    }

    assert settings_response.status_code == 200
    assert settings_response.json() == {
        "logo_video_url": "/logo_anim.mp4",
        "hero_products": [1, 2, 3, 4],
        "showroom1_products": [2, 3, 4],
        "showroom2_products": [1, 2, 3, 4],
        "links": {},
    }


def test_guest_cart_contract_does_not_require_redis(client: TestClient) -> None:
    empty_response = client.get("/api/cart/guest-contract")

    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "cart_id": "guest-contract",
        "items": [],
        "updated_at_ms": 0,
        "ttl_seconds": 2_592_000,
    }

    update_response = client.put(
        "/api/cart/guest-contract",
        json={
            "updated_at_ms": 1234,
            "items": [
                {
                    "id": "1_M_black",
                    "product_id": 1,
                    "title": "Contract product",
                    "price": 1000,
                    "image": "/uploads/contract.webp",
                    "size": "M",
                    "color": "black",
                    "quantity": 1,
                }
            ],
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "status": "ok",
        "cart_id": "guest-contract",
        "items_count": 1,
        "updated_at_ms": 1234,
        "ttl_seconds": 2_592_000,
    }


def test_checkout_response_keeps_order_id_and_provider_urls(client: TestClient) -> None:
    order_response = client.post(
        "/api/orders",
        json={
            "email": "contract@example.test",
            "phone": "+70000000000",
            "first_name": "Contract",
            "delivery_method": "pickup",
            "payment_method": "cash",
            "cart_items": json.dumps(
                [
                    {
                        "product_id": 1,
                        "title": "Contract product",
                        "price": 1000,
                        "quantity": 1,
                        "size": "M",
                        "color": "black",
                        "customization": {"fit": {"lengthCm": 70, "widthCm": 58}},
                    }
                ]
            ),
            "total_price": 1000,
        },
    )

    assert order_response.status_code == 200
    payload = order_response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["order_id"], int)
    assert payload["cdek_uuid"] is None
    assert payload["payment_url"] is None

    detail_response = client.get(f"/api/orders/{payload['order_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["email"] == "contract@example.test"
    assert json.loads(detail["cart_items"])[0]["customization"]["fit"] == {
        "lengthCm": 70,
        "widthCm": 58,
    }


def test_authentication_error_contract(client: TestClient) -> None:
    response = client.post(
        "/api/auth/email/verify",
        json={"email": "missing@example.test", "code": "0000"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid code"}


def test_email_authentication_round_trip_keeps_bearer_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered_code: dict[str, str] = {}

    def capture_code(email: str, code: str) -> bool:
        delivered_code[email] = code
        return True

    legacy_main = importlib.import_module("main")
    monkeypatch.setattr(legacy_main.email_service, "send_auth_otp", capture_code)

    email = "auth-contract@example.test"
    request_response = client.post(
        "/api/auth/email/request",
        json={"email": email},
    )
    assert request_response.status_code == 200
    assert request_response.json()["status"] == "sent"
    assert len(delivered_code[email]) == 4

    verify_response = client.post(
        "/api/auth/email/verify",
        json={"email": email, "code": delivered_code[email]},
    )
    assert verify_response.status_code == 200
    session = verify_response.json()
    assert isinstance(session["token"], str)
    assert session["user"]["email"] == email

    profile_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {session['token']}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == email


def test_refactored_entrypoint_preserves_legacy_product_route(
    legacy_app: FastAPI,
) -> None:
    from app.core.config import get_settings
    from app.factory import create_app

    application = create_app(
        settings=get_settings(),
        legacy_app=legacy_app,
    )

    with TestClient(application) as facade_client:
        health_response = facade_client.get("/health/live")
        products_response = facade_client.get("/api/products")

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert products_response.status_code == 200
    assert len(products_response.json()) == 4
