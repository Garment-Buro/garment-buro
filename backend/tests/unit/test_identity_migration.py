from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.migration import (
    IdentityMigrationService,
    LegacyIdentityPlanner,
    TargetIdentityNotEmptyError,
)
from app.modules.identity.models import (
    IdentityMigrationRun,
    OtpChallenge,
    Permission,
    Role,
    User,
    UserRole,
)


def create_legacy_identity(tmp_path: Path) -> Path:
    database_path = tmp_path / "legacy-users.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email VARCHAR,
                telegram_id VARCHAR,
                first_name VARCHAR,
                last_name VARCHAR,
                username VARCHAR,
                created_at DATETIME,
                phone VARCHAR,
                gender VARCHAR,
                birth_date VARCHAR,
                height FLOAT,
                weight FLOAT,
                otp_code VARCHAR,
                otp_expiry DATETIME
            );
            """
        )
        connection.execute(
            """
            INSERT INTO users (
                id, email, first_name, created_at, phone, gender, birth_date,
                height, weight, otp_code, otp_expiry
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                7,
                "Customer@Example.TEST",
                "Customer",
                "2026-08-10 12:00:00",
                "+79990000000",
                "female",
                "2000-01-02",
                170.5,
                60.25,
                "1234",
                "2026-08-10 12:10:00",
            ),
        )
        connection.commit()
    return database_path


def test_identity_migration_is_deterministic_and_drops_plaintext_otp(tmp_path: Path) -> None:
    legacy_database = create_legacy_identity(tmp_path)
    database_before = legacy_database.read_bytes()
    planner = LegacyIdentityPlanner()

    first = planner.build(legacy_database)
    second = planner.build(legacy_database)

    assert first.valid
    assert first.fingerprint == second.fingerprint
    assert first.report()["counts"] == {"users": 1, "discarded_legacy_otp": 1}
    assert first.users[0].email_normalized == "customer@example.test"
    assert first.users[0].birth_date.isoformat() == "2000-01-02"
    assert "Customer@Example.TEST" not in json.dumps(first.report())
    assert database_before == legacy_database.read_bytes()

    with sqlite3.connect(legacy_database) as connection:
        connection.execute("UPDATE users SET first_name = 'Changed' WHERE id = 7")
        connection.commit()
    assert planner.build(legacy_database).fingerprint != first.fingerprint


def test_identity_migration_applies_once_with_customer_role(tmp_path: Path) -> None:
    legacy_database = create_legacy_identity(tmp_path)
    plan = LegacyIdentityPlanner().build(legacy_database)
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'target-users.db'}",
    )

    async def scenario() -> None:
        database = DatabaseManager(settings)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with database.session() as session:
            result = await IdentityMigrationService().apply(session, plan)
        assert result.users == 1
        assert result.fingerprint_sha256 == plan.fingerprint

        async with database.session() as session:
            counts = {
                "users": await session.scalar(select(func.count()).select_from(User)),
                "roles": await session.scalar(select(func.count()).select_from(Role)),
                "permissions": await session.scalar(select(func.count()).select_from(Permission)),
                "user_roles": await session.scalar(select(func.count()).select_from(UserRole)),
                "otp": await session.scalar(select(func.count()).select_from(OtpChallenge)),
                "runs": await session.scalar(
                    select(func.count()).select_from(IdentityMigrationRun)
                ),
            }
            stored = await session.scalar(select(User))
        assert counts == {
            "users": 1,
            "roles": 3,
            "permissions": 10,
            "user_roles": 1,
            "otp": 0,
            "runs": 1,
        }
        assert stored is not None
        assert stored.id == 7
        assert stored.email == "Customer@Example.TEST"
        assert stored.email_verified_at is None

        with pytest.raises(TargetIdentityNotEmptyError, match="must be empty"):
            async with database.session() as session:
                await IdentityMigrationService().apply(session, plan)
        await database.shutdown()

    asyncio.run(scenario())


def test_identity_planner_rejects_case_insensitive_duplicate_email(tmp_path: Path) -> None:
    legacy_database = create_legacy_identity(tmp_path)
    with sqlite3.connect(legacy_database) as connection:
        connection.execute(
            """
            INSERT INTO users (id, email, created_at)
            VALUES (?, ?, ?)
            """,
            (8, "customer@example.test", "2026-08-10 12:01:00"),
        )
        connection.commit()

    plan = LegacyIdentityPlanner().build(legacy_database)

    assert not plan.valid
    assert any("Users 7 and 8 share one normalized email" in error for error in plan.errors)


def test_identity_apply_requires_reviewed_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    legacy_database = create_legacy_identity(tmp_path)
    from scripts.migrate_legacy_identity import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "migrate_legacy_identity",
            "--sqlite-db",
            str(legacy_database),
            "--apply",
        ],
    )
    assert main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["apply_error"] == "--expect-fingerprint is required with --apply"
