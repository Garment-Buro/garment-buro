from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.base import Base
from app.db.session import DatabaseManager
from app.factory import create_app
from app.modules.identity.cutover import verify_identity_cutover
from app.modules.identity.models import IdentityMigrationRun, UserStatus
from app.modules.identity.repository import IdentityRepository
from app.modules.notifications.crypto import (
    EncryptedNotificationPayload,
    NotificationPayloadCodec,
)
from app.modules.orders.models import LegacyOrderImport, Order
from tests.migration_checks import check_migration

FINGERPRINT = "f" * 64
JWT_SECRET = "j" * 32
OTP_PEPPER = "p" * 32
NOTIFICATION_KEY = base64.urlsafe_b64encode(b"n" * 32).decode("ascii").rstrip("=")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'target.db'}",
        identity_api_enabled=True,
        identity_legacy_token_grace_until=datetime.now(timezone.utc) + timedelta(days=1),
        jwt_secret=JWT_SECRET,
        identity_otp_pepper=OTP_PEPPER,
        notification_encryption_key=NOTIFICATION_KEY,
    )


def _seed_target(settings: Settings) -> None:
    async def seed() -> None:
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                await IdentityRepository().ensure_system_authorization(session)
                session.add(
                    Order(
                        id=10,
                        email="Customer@Example.TEST",
                        email_normalized="customer@example.test",
                        phone="+79990000001",
                        first_name="Customer",
                        items_subtotal=Decimal("1200.00"),
                        delivery_price=Decimal("0.00"),
                        total_price=Decimal("1200.00"),
                        request_fingerprint_sha256="a" * 64,
                        legacy_import=LegacyOrderImport(
                            source_order_id=10,
                            source_row_sha256="a" * 64,
                            raw_cart_items=json.dumps([{"title": "Owned item", "quantity": 1}]),
                            legacy_total_price=Decimal("1200.00"),
                        ),
                    )
                )
                session.add(
                    IdentityMigrationRun(
                        fingerprint_sha256=FINGERPRINT,
                        users_count=0,
                    )
                )
                await session.commit()
        finally:
            await database.shutdown()

    asyncio.run(seed())


def _latest_otp(target_path: Path) -> tuple[str, str]:
    with sqlite3.connect(target_path) as connection:
        row = connection.execute(
            """
            SELECT payload_ciphertext, payload_nonce, payload_tag,
                   encryption_key_version, deduplication_key
            FROM notification_outbox
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    assert row is not None
    payload = NotificationPayloadCodec.from_base64_key(NOTIFICATION_KEY).decrypt(
        EncryptedNotificationPayload(
            ciphertext=row[0],
            nonce=row[1],
            tag=row[2],
            key_version=row[3],
        )
    )
    return str(payload["code"]), str(row[4])


def _login(client: TestClient, target_path: Path, email: str) -> tuple[str, dict[str, object]]:
    requested = client.post("/api/auth/email/request", json={"email": email})
    assert requested.status_code == 200
    assert requested.json() == {"status": "sent"}
    code, deduplication_key = _latest_otp(target_path)
    assert deduplication_key.startswith("otp:challenge:")
    verified = client.post(
        "/api/auth/email/verify",
        json={"email": email, "code": code},
    )
    assert verified.status_code == 200
    payload = verified.json()
    return str(payload["token"]), payload["user"]


def test_guarded_identity_api_preserves_contract_and_secures_order_ownership(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "target.db"
    settings = _settings(tmp_path)
    _seed_target(settings)

    application = create_app(
        settings=settings,
        database=DatabaseManager(settings),
    )
    with TestClient(application) as client:
        invalid = client.post(
            "/api/auth/email/verify",
            json={"email": "missing@example.test", "code": "0000"},
        )
        assert invalid.status_code == 400
        assert invalid.json() == {"detail": "Invalid code"}

        token, user = _login(client, target_path, "Customer@Example.TEST")
        assert user["email"] == "Customer@Example.TEST"
        assert client.cookies.get("gb_refresh")

        headers = {"Authorization": f"Bearer {token}"}
        profile = client.get("/api/auth/me", headers=headers)
        assert profile.status_code == 200
        assert profile.headers.get("cache-control") == "no-store"
        assert profile.json()["email"] == "Customer@Example.TEST"

        access = client.get("/api/auth/access", headers=headers)
        assert access.status_code == 200
        assert access.headers["Cache-Control"] == "no-store"
        assert access.json() == {
            "roles": ["customer"],
            "permissions": [
                "orders.read_own",
                "profile.read_own",
                "profile.write_own",
            ],
        }

        updated = client.put(
            "/api/auth/me",
            headers=headers,
            json={
                "first_name": "Анна",
                "phone": "+79990000001",
                "email": "must-not-change@example.test",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["first_name"] == "Анна"
        assert updated.json()["email"] == "Customer@Example.TEST"

        orders = client.get("/api/auth/orders", headers=headers)
        assert orders.headers.get("cache-control") == "no-store"
        assert orders.status_code == 200
        assert [order["id"] for order in orders.json()["items"]] == [10]
        assert "cart_items" not in orders.json()["items"][0]
        assert orders.json()["next_cursor"] is None

        email_request = client.post(
            "/api/auth/me/email/request",
            headers=headers,
            json={"email": "changed@example.test"},
        )
        assert email_request.status_code == 200
        email_code, _ = _latest_otp(target_path)
        email_verified = client.post(
            "/api/auth/me/email/verify",
            headers=headers,
            json={"email": "changed@example.test", "code": email_code},
        )
        assert email_verified.status_code == 200
        assert email_verified.json()["email"] == "changed@example.test"

        orders_after_email_change = client.get("/api/auth/orders", headers=headers)
        assert [order["id"] for order in orders_after_email_change.json()["items"]] == [10]
        assert client.get("/api/legacy-probe").status_code == 404

        deleted = client.delete("/api/auth/me", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json() == {"status": "deleted"}
        assert client.get("/api/auth/me", headers=headers).status_code == 401

    with sqlite3.connect(target_path) as connection:
        claim = connection.execute(
            "SELECT user_id, legacy_order_id, identifier_digest FROM legacy_order_claims"
        ).fetchone()
        deleted_user = connection.execute(
            "SELECT status, email, phone, first_name FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
        notification_rows = connection.execute(
            """
            SELECT status, payload_ciphertext, last_error_code, discard_after
            FROM notification_outbox
            ORDER BY id
            """
        ).fetchall()
    assert claim is not None
    assert claim[1] == 10
    assert "customer@example.test" not in "|".join(str(value) for value in claim)
    assert deleted_user == (UserStatus.DELETED.value, None, None, None)
    assert len(notification_rows) == 2
    assert all(row[0] == "dead" for row in notification_rows)
    assert all(row[1] is None for row in notification_rows)
    assert all(row[2] == "challenge_consumed" for row in notification_rows)
    assert all(row[3] is not None for row in notification_rows)


def test_refresh_rotation_reuse_csrf_and_legacy_token_grace(tmp_path: Path) -> None:
    target_path = tmp_path / "target.db"
    settings = _settings(tmp_path)
    _seed_target(settings)
    application = create_app(settings=settings, database=DatabaseManager(settings))

    with TestClient(application) as client:
        token, user = _login(client, target_path, "refresh@example.test")
        legacy_token = jwt.encode(
            {
                "sub": str(user["id"]),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            JWT_SECRET,
            algorithm="HS256",
        )
        assert (
            client.post(
                "/api/auth/session/migrate",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {legacy_token}"},
            ).status_code
            == 200
        )

        migrated = client.post(
            "/api/auth/session/migrate",
            headers={"Authorization": f"Bearer {legacy_token}"},
        )
        assert migrated.status_code == 200
        token = migrated.json()["token"]
        assert migrated.json()["user"]["id"] == user["id"]

        old_refresh = client.cookies.get("gb_refresh")
        assert old_refresh
        rejected = client.post(
            "/api/auth/refresh",
            headers={"Origin": "https://evil.example"},
        )
        assert rejected.status_code == 403
        assert client.cookies.get("gb_refresh") == old_refresh

        rotated = client.post("/api/auth/refresh")
        assert rotated.status_code == 200
        rotated_token = rotated.json()["token"]
        assert rotated_token != token
        assert client.cookies.get("gb_refresh") != old_refresh
        assert (
            client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code
            == 401
        )

        client.cookies.set("gb_refresh", old_refresh, path="/api/auth")
        reuse = client.post("/api/auth/refresh")
        assert reuse.status_code == 401
        assert (
            client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {rotated_token}"},
            ).status_code
            == 401
        )


def test_auth_methods_password_and_disabled_phone_contract(tmp_path: Path) -> None:
    target_path = tmp_path / "target.db"
    settings = _settings(tmp_path)
    _seed_target(settings)
    application = create_app(settings=settings, database=DatabaseManager(settings))

    with TestClient(application) as client:
        methods = client.get("/api/auth/methods")
        assert methods.status_code == 200
        indexed = {item["code"]: item for item in methods.json()["methods"]}
        assert indexed["email"]["enabled"] is True
        assert indexed["password"]["enabled"] is True
        assert indexed["phone"] == {
            "code": "phone",
            "kind": "otp",
            "enabled": False,
            "reason": "provider_not_configured",
        }
        assert indexed["telegram"]["enabled"] is False

        assert (
            client.post("/api/auth/phone/request", json={"phone": "+79991234567"}).status_code
            == 503
        )
        assert (
            client.post(
                "/api/auth/telegram",
                json={"id": 1, "auth_date": 1, "hash": "a" * 64},
            ).status_code
            == 503
        )

        token, user = _login(client, target_path, "password-contract@example.test")
        password_set = client.put(
            "/api/auth/password",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_password": "correct horse battery staple"},
        )
        assert password_set.status_code == 200
        assert password_set.json() == {"status": "password_updated"}

        logged_in = client.post(
            "/api/auth/password/login",
            json={
                "identifier": "PASSWORD-CONTRACT@example.test",
                "password": "correct horse battery staple",
            },
        )
        assert logged_in.status_code == 200
        assert logged_in.json()["user"]["id"] == user["id"]
        assert (
            client.post(
                "/api/auth/password/login",
                json={
                    "identifier": "password-contract@example.test",
                    "password": "incorrect password value",
                },
            ).status_code
            == 401
        )


def test_identity_cutover_refuses_unreviewed_target(tmp_path: Path) -> None:
    seeded_settings = _settings(tmp_path)
    _seed_target(seeded_settings)
    with pytest.raises(ConfigurationError, match="fingerprint is not present"):
        check_migration(seeded_settings, verify_identity_cutover, "e" * 64)


def test_identity_cutover_refuses_tampered_counts_and_permissions(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_target(settings)
    target_path = tmp_path / "target.db"

    with sqlite3.connect(target_path) as connection:
        connection.execute("UPDATE identity_migration_runs SET users_count = 1")
    with pytest.raises(ConfigurationError, match="fewer users"):
        check_migration(settings, verify_identity_cutover, FINGERPRINT)

    with sqlite3.connect(target_path) as connection:
        connection.execute("UPDATE identity_migration_runs SET users_count = 0")
        connection.execute(
            """
            DELETE FROM role_permissions
            WHERE role_id = (SELECT id FROM roles WHERE name = 'customer')
              AND permission_id = (
                  SELECT id FROM permissions WHERE code = 'orders.read_own'
              )
            """
        )
    with pytest.raises(ConfigurationError, match="permissions are incomplete"):
        check_migration(settings, verify_identity_cutover, FINGERPRINT)
