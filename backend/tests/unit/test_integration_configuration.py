from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import IntegrationNotConfiguredError
from cdek_client import CdekClient
from email_service import send_email
from payments import YooKassaClient


@pytest.fixture()
def settings_without_integrations() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        cdek_client_id=None,
        cdek_client_secret=None,
        yookassa_shop_id=None,
        yookassa_api_key=None,
        smtp_password=None,
    )


def test_cdek_refuses_network_access_without_credentials(
    settings_without_integrations: Settings,
) -> None:
    client = CdekClient(settings=settings_without_integrations)

    with pytest.raises(IntegrationNotConfiguredError, match="CDEK"):
        asyncio.run(client.get_token())


def test_yookassa_refuses_network_access_without_credentials(
    settings_without_integrations: Settings,
) -> None:
    client = YooKassaClient(settings=settings_without_integrations)

    with pytest.raises(IntegrationNotConfiguredError, match="YooKassa"):
        client.get_payment_status("not-used")


def test_smtp_refuses_network_access_without_password(
    settings_without_integrations: Settings,
) -> None:
    assert not send_email(
        "recipient@example.test",
        "Contract subject",
        "<p>Contract body</p>",
        settings=settings_without_integrations,
    )


def test_provider_modules_do_not_embed_environment_fallback_secrets() -> None:
    backend_dir = Path(__file__).resolve().parents[2]

    for source_name in ("cdek_client.py", "payments.py", "email_service.py"):
        source = (backend_dir / source_name).read_text(encoding="utf-8")
        assert "os.getenv" not in source

    payment_source = (backend_dir / "payments.py").read_text(encoding="utf-8")
    cdek_source = (backend_dir / "cdek_client.py").read_text(encoding="utf-8")
    assert "YOOKASSA_API_KEY =" not in payment_source
    assert "CDEK_CLIENT_SECRET =" not in cdek_source
