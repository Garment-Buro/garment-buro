from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.factory import create_app
from app.modules.payments.models import PaymentEvent
from app.modules.payments.service import MAX_PAYMENT_WEBHOOK_BYTES

PROVIDER_IP = "185.71.76.1"
PROVIDER_PAYMENT_ID = "2c111111-000f-5000-a000-111111111111"


def _settings(path: Path, **values: object) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        payment_webhook_v2_enabled=True,
        **values,
    )


def _webhook_body(*, include_type: bool = True, amount: str = "125.50") -> bytes:
    body: dict[str, object] = {
        "event": "payment.succeeded",
        "object": {
            "id": PROVIDER_PAYMENT_ID,
            "status": "succeeded",
            "amount": {"value": amount, "currency": "RUB"},
            "metadata": {"order_id": "17"},
            "payment_method": {"type": "bank_card", "title": "Bank card *0000"},
            "paid": True,
            "test": True,
            "created_at": "2026-08-11T12:00:00Z",
            "captured_at": "2026-08-11T12:01:00Z",
            "customer": {"email": "must-not-persist@example.test"},
        },
    }
    if include_type:
        body["type"] = "notification"
    return json.dumps(body).encode()


def _application(settings: Settings, database: DatabaseManager) -> FastAPI:
    legacy = FastAPI()

    @legacy.post("/api/webhooks/yookassa")
    async def legacy_webhook() -> dict[str, str]:
        return {"source": "legacy"}

    return create_app(settings=settings, database=database, legacy_app=legacy)


def _create_schema(database: DatabaseManager) -> None:
    async def scenario() -> None:
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(scenario())


def test_guarded_webhook_commits_before_equal_duplicate_acknowledgement(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path / "webhook.db")
    database = DatabaseManager(settings)
    _create_schema(database)
    application = _application(settings, database)
    body = _webhook_body()

    with TestClient(application, client=(PROVIDER_IP, 50_000)) as client:
        first = client.post(
            "/api/webhooks/yookassa",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        duplicate = client.post(
            "/api/webhooks/yookassa",
            content=body,
            headers={"Content-Type": "application/json"},
        )

    assert first.status_code == 200 and duplicate.status_code == 200
    assert first.json() == duplicate.json() == {"status": "ok"}
    assert first.headers["cache-control"] == "no-store"

    async def verify() -> None:
        await database.startup()
        async with database.session() as session:
            assert (
                int(await session.scalar(select(func.count()).select_from(PaymentEvent)) or 0) == 1
            )
            event = await session.scalar(select(PaymentEvent))
            assert event is not None
            assert event.source_ip == PROVIDER_IP
            assert event.payment_attempt_id is None
            assert event.status == "received"
            assert event.payload_sha256 not in body.decode()
        await database.shutdown()

    asyncio.run(verify())


def test_guarded_webhook_accepts_forwarding_only_from_configured_proxy(
    tmp_path: Path,
) -> None:
    settings = _settings(
        tmp_path / "proxy.db",
        payment_webhook_trusted_proxy_cidrs="10.0.0.0/8",
    )
    database = DatabaseManager(settings)
    _create_schema(database)
    application = _application(settings, database)

    with TestClient(application, client=("10.1.2.3", 50_000)) as client:
        accepted = client.post(
            "/api/webhooks/yookassa",
            content=_webhook_body(),
            headers={
                "Content-Type": "application/json",
                "X-Forwarded-For": PROVIDER_IP,
            },
        )
    assert accepted.status_code == 200


def test_guarded_webhook_rejects_untrusted_source_spoof_and_invalid_payloads(
    tmp_path: Path,
) -> None:
    settings = _settings(
        tmp_path / "rejected.db",
        payment_webhook_trusted_proxy_cidrs="10.0.0.0/8",
    )
    database = DatabaseManager(settings)
    _create_schema(database)
    application = _application(settings, database)

    with TestClient(application, client=("198.51.100.7", 50_000)) as direct_client:
        spoofed = direct_client.post(
            "/api/webhooks/yookassa",
            content=_webhook_body(),
            headers={"Content-Type": "application/json", "X-Forwarded-For": PROVIDER_IP},
        )
    assert spoofed.status_code == 404

    with TestClient(application, client=(PROVIDER_IP, 50_000)) as provider_client:
        assert (
            provider_client.post(
                "/api/webhooks/yookassa",
                content=_webhook_body(),
                headers={"Content-Type": "text/plain"},
            ).status_code
            == 415
        )
        assert (
            provider_client.post(
                "/api/webhooks/yookassa",
                content=_webhook_body(include_type=False),
                headers={"Content-Type": "application/json"},
            ).status_code
            == 400
        )
        assert (
            provider_client.post(
                "/api/webhooks/yookassa",
                content=b"x" * (MAX_PAYMENT_WEBHOOK_BYTES + 1),
                headers={"Content-Type": "application/json"},
            ).status_code
            == 413
        )


def test_default_flag_preserves_legacy_webhook_owner() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=False,
        payment_webhook_v2_enabled=False,
    )
    legacy = FastAPI()

    @legacy.post("/api/webhooks/yookassa")
    async def legacy_webhook() -> dict[str, str]:
        return {"source": "legacy"}

    application = create_app(settings=settings, legacy_app=legacy)
    with TestClient(application) as client:
        response = client.post("/api/webhooks/yookassa", json={})

    assert response.status_code == 200
    assert response.json() == {"source": "legacy"}
