import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from app.modules.identity.models import User, UserRole
from app.modules.identity.router import router as identity_router
from app.modules.production.auth_models import ProductionCredential
from app.modules.production.auth_service import (
    issue_code,
    limit_login,
    login,
    resolve_session,
    revoke_code,
)
from app.modules.production.router import router
from tests.unit.test_production_terminal import setup

PEPPER = "test-production-code-pepper-which-is-not-a-real-secret"


def test_personal_code_rotation_and_session_revocation(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, _, _):
            async with db.session() as session:
                code = await issue_code(session, user_id=2, station="cut", pepper=PEPPER)
                await session.commit()
                assert len(code) == 6 and code.startswith("2") and code.isascii()
                stored = await session.scalar(select(ProductionCredential))
                assert stored.code_digest != code and len(stored.code_digest) == 64
                token = await login(
                    session, code=code, pepper=PEPPER, now=datetime.now(timezone.utc)
                )
                assert (await resolve_session(session, token)).id == 2
                new_code = await issue_code(session, user_id=2, station="cut", pepper=PEPPER)
                await session.commit()
                assert new_code != code
                assert await resolve_session(session, token) is None
                assert (
                    await login(session, code=code, pepper=PEPPER, now=datetime.now(timezone.utc))
                    is None
                )
                await revoke_code(session, user_id=2)
                await session.commit()
                assert (
                    await login(
                        session, code=new_code, pepper=PEPPER, now=datetime.now(timezone.utc)
                    )
                    is None
                )

    asyncio.run(scenario())


def test_blocked_and_expired_sessions(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, _, _):
            async with db.session() as session:
                code = await issue_code(session, user_id=2, station="cut", pepper=PEPPER)
                await session.commit()
                token = await login(
                    session,
                    code=code,
                    pepper=PEPPER,
                    now=datetime.now(timezone.utc) - timedelta(hours=9),
                )
                assert await resolve_session(session, token) is None
                token = await login(
                    session, code=code, pepper=PEPPER, now=datetime.now(timezone.utc)
                )
                user = await session.get(User, 2)
                user.status = "blocked"
                await session.commit()
                assert await resolve_session(session, token) is None

    asyncio.run(scenario())


def test_removed_role_revokes_access(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, _, _):
            async with db.session() as session:
                code = await issue_code(session, user_id=2, station="cut", pepper=PEPPER)
                await session.commit()
                token = await login(
                    session, code=code, pepper=PEPPER, now=datetime.now(timezone.utc)
                )
                role = await session.scalar(select(UserRole).where(UserRole.user_id == 2))
                await session.delete(role)
                await session.commit()
                assert await resolve_session(session, token) is None

    asyncio.run(scenario())


def test_rate_limits_survive_failed_login_transactions(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, _, _):
            now = datetime.now(timezone.utc)
            for i in range(11):
                async with db.session() as session:
                    assert await limit_login(session, client_ip="test", pepper=PEPPER, now=now) is (
                        i < 10
                    )
                    await session.rollback()
            async with db.session() as session:
                assert await limit_login(
                    session, client_ip="test", pepper=PEPPER, now=now + timedelta(minutes=16)
                )

    asyncio.run(scenario())


def test_pin_api_cookie_csrf_and_logout(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, _):
            app = FastAPI()
            app.include_router(router)
            app.include_router(identity_router)
            app.state.identity_service = None
            app.state.database = db
            app.state.settings = service.settings.model_copy(
                update={
                    "production_terminal_enabled": True,
                    "identity_otp_pepper": SecretStr(PEPPER),
                    "cors_origins": "https://test",
                    "public_base_url": "https://test",
                }
            )
            async with db.session() as session:
                code = await issue_code(session, user_id=2, station="cut", pepper=PEPPER)
                await session.commit()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="https://test"
            ) as client:
                assert (await client.get("/api/production/me")).status_code == 401
                assert (
                    await client.post(
                        "/api/production/auth/login",
                        json={"code": code},
                        headers={"Origin": "https://evil.test"},
                    )
                ).status_code == 403
                assert (
                    await client.post("/api/production/auth/login", json={"code": "12345"})
                ).status_code == 422
                result = await client.post("/api/production/auth/login", json={"code": code})
                assert result.status_code == 200, result.text
                cookie = result.headers["set-cookie"].lower()
                assert (
                    "httponly" in cookie
                    and "samesite=strict" in cookie
                    and "path=/api/production" in cookie
                )
                assert (await client.get("/api/production/me")).json()["id"] == 2
                assert (await client.get("/api/auth/me")).status_code == 401
                assert (await client.post("/api/production/auth/logout")).status_code == 200
                assert (await client.get("/api/production/me")).status_code == 401

    asyncio.run(scenario())


def test_cannot_issue_code_for_customer_or_wrong_station(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, _, _):
            async with db.session() as session:
                with pytest.raises(ValueError):
                    await issue_code(session, user_id=2, station="tech", pepper=PEPPER)
                with pytest.raises(ValueError):
                    await issue_code(session, user_id=999, station="tech", pepper=PEPPER)

    asyncio.run(scenario())
