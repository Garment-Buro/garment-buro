import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import delete

from app.modules.identity.models import RoleName, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.production.auth_service import issue_code
from app.modules.production.router import router
from tests.unit.test_order_workflow import NOW, setup, work


def test_admin_terminal_moderation_persists_decision_before_capture(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, provider, _, _):
            app = FastAPI()
            app.include_router(router)
            app.state.database = db
            app.state.settings = db.settings.model_copy(
                update={
                    "production_terminal_enabled": True,
                    "identity_otp_pepper": SecretStr("test-only"),
                    "public_base_url": "https://test",
                    "cors_origins": "https://test",
                }
            )
            async with db.session() as session:
                role = await IdentityRepository().get_role(session, RoleName.PRODUCTION_ADMIN)
                await session.execute(delete(UserRole).where(UserRole.user_id == 1))
                session.add(UserRole(user_id=1, role_id=role.id))
                await session.flush()
                code = await issue_code(session, user_id=1, station="admin", pepper="test-only")
                await session.commit()
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                assert (
                    await client.post("/api/production/auth/login", json={"code": code})
                ).status_code == 200
                detail = (await client.get("/api/production/admin/orders/1")).json()
                assert detail["moderation"]["state"] == "moderation"
                body = {
                    "expected_version": detail["moderation"]["version"],
                    "decision": "approve",
                    "note": "Техкарты проверены",
                }
                headers = {"Idempotency-Key": "admin-moderation-retry"}
                response = await client.post(
                    "/api/production/admin/orders/1/moderation", json=body, headers=headers
                )
                assert response.status_code == 200, response.text
                assert response.json()["state"] == "capture_pending"
                assert (
                    provider.captures == []
                )  # HTTP commits an intent, the worker talks to the bank.
                replay = await client.post(
                    "/api/production/admin/orders/1/moderation", json=body, headers=headers
                )
                assert replay.json() == response.json()
                assert (
                    await client.post(
                        "/api/production/admin/orders/1/moderation",
                        json=body | {"decision": "reject"},
                        headers=headers,
                    )
                ).status_code == 409
            now = max(NOW, datetime.now(timezone.utc)) + timedelta(seconds=1)
            await work(db, provider, now=now)
            await work(db, provider, now=now)
            assert len(provider.captures) == 1

    asyncio.run(scenario())
