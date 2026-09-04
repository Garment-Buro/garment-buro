from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.config import AppEnvironment, Settings
from app.modules.qr_codes.schemas import QrCodeSurface
from app.modules.qr_codes.service import QrCodeService, QrCodeValidationError


def _service() -> QrCodeService:
    return QrCodeService(
        Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            public_base_url="https://site.example.test",
            partner_public_base_url="https://partner.example.test",
            widget_public_base_url="https://widget.example.test",
        )
    )


def test_qr_code_service_builds_targets_only_on_configured_surfaces() -> None:
    service = _service()

    assert service.build_target("/nikitamoiseev?look=5", QrCodeSurface.SITE) == (
        "https://site.example.test/nikitamoiseev?look=5"
    )
    assert service.build_target("/partner", QrCodeSurface.PARTNER) == (
        "https://partner.example.test/partner"
    )
    assert service.build_target("/workspace", QrCodeSurface.WIDGET) == (
        "https://widget.example.test/workspace"
    )


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.example/path",
        "//evil.example/path",
        "/%2F%2Fevil.example/path",
        "/landing/../admin",
        "/landing/%2e%2e/admin",
        "/landing\\admin",
        "/landing\nadmin",
    ],
)
def test_qr_code_service_rejects_unsafe_targets(path: str) -> None:
    with pytest.raises(QrCodeValidationError):
        _service().build_target(path, QrCodeSurface.SITE)


def test_qr_code_service_generates_deterministic_square_png() -> None:
    service = _service()

    first = service.generate_png("/nikitamoiseev", QrCodeSurface.SITE, 512)
    second = service.generate_png("/nikitamoiseev", QrCodeSurface.SITE, 512)

    assert first.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert first.content == second.content
    assert first.etag == second.etag
    assert first.target_url == "https://site.example.test/nikitamoiseev"
    with Image.open(io.BytesIO(first.content)) as image:
        assert image.size == (512, 512)
        assert image.mode == "RGB"


def test_qr_code_service_rejects_non_origin_surface_configuration() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        partner_public_base_url="https://partner.example.test/unexpected-path",
    )

    with pytest.raises(RuntimeError, match=r"absolute HTTP\(S\) origins"):
        QrCodeService(settings)


def test_qr_code_service_limits_utf8_payload_size() -> None:
    with pytest.raises(QrCodeValidationError, match="root-relative site path"):
        _service().build_target("/" + ("я" * 1_023), QrCodeSurface.SITE)
