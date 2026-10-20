"""Rehearse auth upgrades in owned test databases using real Alembic and HTTP.

This helper runs in the current production image without pytest.
It never connects to a database whose name does not start with test_.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import multiprocessing
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import make_url, pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.db import models as database_models  # noqa: F401
from app.db.base import Base
from app.db.schema import comparison_metadata
from app.db.session import DatabaseManager
from app.modules.identity.models import RoleName, UserRole
from app.modules.identity.passwords import PasswordSecurity
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import TokenSecurity
from app.modules.notifications.factory import build_notification_outbox_service
from app.modules.notifications.models import NotificationChannel

BACKEND = Path(__file__).resolve().parents[1]
STARTS = ("base", "20260929_0055", "20261012_0056", "20261019_0080")
HEAD = "20261020_0081"
JWT_SECRET, OTP_PEPPER = "j" * 32, "p" * 32
PASSWORD = "synthetic correct horse battery staple"
EMAIL = "upgrade@example.test"
TELEGRAM_SUBJECT = "987654321"
BOT_TOKEN = "123456:synthetic-upgrade-test-token"
REFRESH_TOKEN = "synthetic-upgrade-refresh-token"


def settings(url):
    return Settings(
        _env_file=None,
        app_env="test",
        database_enabled=True,
        database_url=url,
        identity_api_enabled=True,
        jwt_secret=JWT_SECRET,
        identity_otp_pepper=OTP_PEPPER,
        notification_encryption_key=base64.urlsafe_b64encode(b"n" * 32).decode(),
        identity_telegram_auth_enabled=True,
        telegram_bot_token=BOT_TOKEN,
    )


def migrate(url, *command):
    # Alembic reads Settings; an empty working directory prevents local .env use.
    with tempfile.TemporaryDirectory(prefix="gb-auth-migrations-") as directory:
        root = Path(directory)
        shutil.copytree(BACKEND / "migrations", root / "migrations")
        shutil.copyfile(BACKEND / "alembic.ini", root / "alembic.ini")
        environment = {
            k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "LANG") if k in os.environ
        }
        environment.update(
            PYTHONPATH=str(BACKEND), APP_ENV="test", DATABASE_ENABLED="true", DATABASE_URL=url
        )
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *command],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=240,
        )
        assert result.returncode == 0, result.stderr or result.stdout


async def manage_database(source, name, *, create):
    engine = create_async_engine(source, poolclass=pool.NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text(
                    f'CREATE DATABASE "{name}"'
                    if create
                    else f'DROP DATABASE "{name}" WITH (FORCE)'
                )
            )
    finally:
        await engine.dispose()


async def seed(url, *, auth_present):
    now = datetime.now(timezone.utc)
    database = DatabaseManager(settings(url))
    await database.startup()
    try:
        async with database.session() as session:
            repository = IdentityRepository()
            await repository.ensure_system_authorization(session)
            user_id = await session.scalar(
                text(
                    "INSERT INTO users (email,email_normalized,first_name,email_verified_at) "
                    "VALUES (:email,:email,'Retained user',:now) RETURNING id"
                ),
                {"email": EMAIL, "now": now},
            )
            telegram_user = await session.scalar(
                text(
                    "INSERT INTO users (telegram_id,first_name) VALUES (:subject,'Telegram user') RETURNING id"
                ),
                {"subject": TELEGRAM_SUBJECT},
            )
            customer = await session.scalar(
                text("SELECT id FROM roles WHERE name=:name"), {"name": RoleName.CUSTOMER.value}
            )
            session.add_all(
                [
                    UserRole(user_id=user_id, role_id=customer),
                    UserRole(user_id=telegram_user, role_id=customer),
                ]
            )
            salt = "a" * 32
            digest = hmac.new(
                OTP_PEPPER.encode(),
                "\0".join([salt, "login", EMAIL, "1234"]).encode(),
                hashlib.sha256,
            ).hexdigest()
            await session.execute(
                text(
                    "INSERT INTO otp_challenges (user_id,purpose,target_email,target_email_normalized,"
                    "code_digest,code_salt,expires_at,max_attempts,active_key) "
                    "VALUES (:user,'login',:email,:email,:digest,:salt,:expires,5,:active)"
                ),
                {
                    "user": user_id,
                    "email": EMAIL,
                    "digest": digest,
                    "salt": salt,
                    "expires": now + timedelta(minutes=10),
                    "active": f"login:{user_id}",
                },
            )
            session_id = str(uuid4())
            await session.execute(
                text(
                    "INSERT INTO refresh_sessions (user_id,session_id,family_id,token_digest,expires_at) "
                    "VALUES (:user,:sid,:family,:digest,:expires)"
                ),
                {
                    "user": user_id,
                    "sid": session_id,
                    "family": str(uuid4()),
                    "digest": hashlib.sha256(REFRESH_TOKEN.encode()).hexdigest(),
                    "expires": now + timedelta(days=1),
                },
            )
            password_hash = None
            if auth_present:
                password_hash = await PasswordSecurity().hash(PASSWORD)
                await session.execute(
                    text(
                        "INSERT INTO password_credentials (user_id,password_hash) VALUES (:user,:hash)"
                    ),
                    {"user": user_id, "hash": password_hash},
                )
                await session.execute(
                    text(
                        "INSERT INTO external_auth_identities (user_id,provider,subject) VALUES (:user,'telegram',:subject)"
                    ),
                    {"user": telegram_user, "subject": TELEGRAM_SUBJECT},
                )
                await build_notification_outbox_service(settings(url)).enqueue_auth_otp(
                    session,
                    recipient=TELEGRAM_SUBJECT,
                    code="1234",
                    purpose="login",
                    expires_minutes=10,
                    deduplication_key="upgrade:telegram:preserved",
                    now=now,
                    discard_after=now + timedelta(minutes=10),
                    channel=NotificationChannel.TELEGRAM,
                )
            await session.commit()
            access, _ = TokenSecurity(JWT_SECRET).create_access_token(
                user_id=user_id, session_id=session_id, now=now
            )
            return {
                "user": user_id,
                "telegram": telegram_user,
                "passwordHash": password_hash,
                "access": access,
            }
    finally:
        await database.shutdown()


async def verify_schema_and_data(url, fixture, *, auth_present):
    engine = create_async_engine(url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            changes = await connection.run_sync(
                lambda sync: compare_metadata(
                    MigrationContext.configure(sync, opts={"compare_type": True}),
                    comparison_metadata(sync.dialect, Base.metadata),
                )
            )
            assert changes == [], changes
            for table, previous in fixture.get("snapshot", {}).items():
                current = (
                    await connection.scalars(text(f"SELECT to_jsonb(t) FROM {table} AS t"))
                ).all()
                columns = set(previous[0]) if previous else set()
                assert sorted(
                    json.dumps({key: row[key] for key in columns}, sort_keys=True)
                    for row in current
                ) == sorted(json.dumps(row, sort_keys=True) for row in previous), (
                    f"Historical data changed in {table}"
                )
            assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            assert await connection.scalar(text("SELECT count(*) FROM users")) == 2
            assert (
                await connection.scalar(
                    text("SELECT first_name FROM users WHERE id=:user"), {"user": fixture["user"]}
                )
                == "Retained user"
            )
            assert (
                await connection.scalar(
                    text("SELECT subject FROM external_auth_identities WHERE user_id=:user"),
                    {"user": fixture["telegram"]},
                )
                == TELEGRAM_SUBJECT
            )
            assert (
                await connection.scalar(text("SELECT code_digest FROM otp_challenges"))
                == hmac.new(
                    OTP_PEPPER.encode(),
                    "\0".join(["a" * 32, "login", EMAIL, "1234"]).encode(),
                    hashlib.sha256,
                ).hexdigest()
            )
            if auth_present:
                assert (
                    await connection.scalar(text("SELECT password_hash FROM password_credentials"))
                    == fixture["passwordHash"]
                )
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM notification_outbox WHERE channel='telegram'")
                    )
                    == 1
                )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_indexes WHERE tablename='password_credentials' AND indexname='ix_password_credentials_user_id'"
                    )
                )
                == 0
            )
    finally:
        await engine.dispose()


async def snapshot_auth_data(url):
    engine = create_async_engine(url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            snapshot = {}
            for table in (
                "users",
                "user_roles",
                "refresh_sessions",
                "otp_challenges",
                "password_credentials",
                "external_auth_identities",
                "notification_outbox",
            ):
                if await connection.scalar(
                    text("SELECT to_regclass(:table)"), {"table": "public." + table}
                ):
                    snapshot[table] = (
                        await connection.scalars(text(f"SELECT to_jsonb(t) FROM {table} AS t"))
                    ).all()
            return snapshot
    finally:
        await engine.dispose()


def serve(url, listener):
    import uvicorn

    from app.factory import create_app

    server = uvicorn.Server(
        uvicorn.Config(create_app(settings=settings(url)), log_level="error", access_log=False)
    )
    server.run(sockets=[listener])


def verify_http(url, fixture, *, auth_present):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    endpoint = f"http://127.0.0.1:{listener.getsockname()[1]}"
    process = multiprocessing.get_context("spawn").Process(target=serve, args=(url, listener))
    process.start()
    listener.close()

    def request(path, *, method="GET", payload=None, headers=None):
        req = Request(
            endpoint + path,
            method=method,
            headers={"Content-Type": "application/json", **(headers or {})},
            data=json.dumps(payload).encode() if payload is not None else None,
        )
        try:
            response = urlopen(req, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response), response.headers

    try:
        deadline = time.monotonic() + 60
        while True:
            assert process.is_alive(), "Test API exited before startup"
            try:
                code, body, _ = request("/api/auth/methods")
                assert code == 200 and any(
                    m["code"] == "password" and m["enabled"] for m in body["methods"]
                )
                break
            except (URLError, TimeoutError, ConnectionResetError):
                assert time.monotonic() < deadline, "Test API startup timeout"
                time.sleep(0.05)
        headers = {"Authorization": "Bearer " + fixture["access"]}
        status, body, response_headers = request("/api/auth/me", headers=headers)
        assert status == 200 and body["id"] == fixture["user"]
        assert response_headers.get("Cache-Control") == "no-store"
        status, body, _ = request(
            "/api/auth/refresh", method="POST", headers={"Cookie": "gb_refresh=" + REFRESH_TOKEN}
        )
        assert status == 200 and body["user"]["id"] == fixture["user"]
        assert request("/api/auth/me", headers=headers)[0] == 401
        headers = {"Authorization": "Bearer " + body["token"]}
        status, body, _ = request(
            "/api/auth/email/verify", method="POST", payload={"email": EMAIL, "code": "1234"}
        )
        assert status == 200 and body["user"]["id"] == fixture["user"]
        if not auth_present:
            status, _, _ = request(
                "/api/auth/password",
                method="PUT",
                headers=headers,
                payload={"new_password": PASSWORD},
            )
            assert status == 200
        status, body, _ = request(
            "/api/auth/password/login",
            method="POST",
            payload={"identifier": EMAIL.upper(), "password": PASSWORD},
        )
        assert status == 200 and body["user"]["id"] == fixture["user"]
        payload = {
            "id": int(TELEGRAM_SUBJECT),
            "auth_date": int(datetime.now(timezone.utc).timestamp()),
            "first_name": "Retained Telegram",
        }
        check = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
        payload["hash"] = hmac.new(
            hashlib.sha256(BOT_TOKEN.encode()).digest(), check.encode(), hashlib.sha256
        ).hexdigest()
        status, body, _ = request("/api/auth/telegram", method="POST", payload=payload)
        assert status == 200 and body["user"]["id"] == fixture["telegram"]
        status, _, _ = request(
            "/api/auth/phone/request", method="POST", payload={"phone": "+79991234567"}
        )
        assert status == 503
    finally:
        process.terminate()
        process.join(15)
        if process.is_alive():
            process.kill()
            process.join(5)
        assert not process.is_alive()


def run_scenario(source_url, start):
    source = make_url(source_url)
    assert source.get_backend_name() == "postgresql"
    assert (source.database or "").startswith("test_"), "Use a disposable test_* database"
    assert start in STARTS
    name = "test_auth_upgrade_" + uuid4().hex
    url = source.set(database=name).render_as_string(hide_password=False)
    asyncio.run(manage_database(source, name, create=True))
    try:
        if start != "base":
            migrate(url, "upgrade", start)
        auth_present = start == "20261012_0056"
        fixture = asyncio.run(seed(url, auth_present=auth_present)) if start != "base" else None
        if fixture is not None:
            fixture["snapshot"] = asyncio.run(snapshot_auth_data(url))
        migrate(url, "upgrade", "head")
        if fixture is None:
            # A fresh database has no historical Telegram user to backfill.
            fixture = asyncio.run(seed(url, auth_present=True))
            auth_present = True
        asyncio.run(verify_schema_and_data(url, fixture, auth_present=auth_present))
        verify_http(url, fixture, auth_present=auth_present)
        return {
            "start": start,
            "head": HEAD,
            "schemaMatchesModels": True,
            "accountDataPreserved": True,
            "oldOtpAccessRefreshAndPasswordHttpPassed": True,
            "telegramIdentityReused": True,
            "phoneProviderDisabled": True,
        }
    finally:
        asyncio.run(manage_database(source, name, create=False))


if __name__ == "__main__":
    for start in STARTS:
        print(json.dumps(run_scenario(os.environ["SCHEMA_TEST_POSTGRES_URL"], start)), flush=True)
