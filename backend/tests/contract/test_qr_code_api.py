from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import AppEnvironment, Settings
from app.factory import create_app


def _client() -> TestClient:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        public_base_url="https://site.example.test",
        partner_public_base_url="https://partner.example.test",
        widget_public_base_url="https://widget.example.test",
    )
    return TestClient(create_app(settings=settings))


def test_qr_code_api_returns_a_cacheable_png_for_a_site_page() -> None:
    with _client() as client:
        response = client.get(
            "/api/qr-code",
            params={"path": "/nikitamoiseev", "size": 256},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.headers["x-qr-target"] == "https://site.example.test/nikitamoiseev"
    assert response.headers["etag"].startswith('"')
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (256, 256)


def test_qr_code_api_supports_only_configured_partner_and_widget_origins() -> None:
    with _client() as client:
        partner = client.get(
            "/api/qr-code",
            params={"path": "/partner", "surface": "partner"},
        )
        widget = client.get(
            "/api/qr-code",
            params={"path": "/workspace", "surface": "widget"},
        )

    assert partner.status_code == 200
    assert partner.headers["x-qr-target"] == "https://partner.example.test/partner"
    assert widget.status_code == 200
    assert widget.headers["x-qr-target"] == "https://widget.example.test/workspace"


def test_qr_code_api_rejects_external_urls_and_oversized_images() -> None:
    with _client() as client:
        external = client.get(
            "/api/qr-code",
            params={"path": "https://evil.example/path"},
        )
        oversized = client.get(
            "/api/qr-code",
            params={"path": "/safe", "size": 4096},
        )

    assert external.status_code == 422
    assert external.json()["detail"]["code"] == "invalid_qr_target"
    assert external.headers["cache-control"] == "no-store"
    assert oversized.status_code == 422
