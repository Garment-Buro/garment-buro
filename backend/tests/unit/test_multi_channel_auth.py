from __future__ import annotations

import asyncio
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.auth_methods.phone import PhoneOtpAuthMethod
from app.modules.identity.exceptions import (
    InvalidCredentialsError,
    InvalidExternalAuthPayloadError,
)
from app.modules.identity.factory import build_auth_method_registry
from app.modules.identity.models import ExternalAuthIdentity, PasswordCredential
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import OtpSecurity, TokenSecurity, normalize_phone
from app.modules.identity.service import IdentityPolicy, IdentityService
from app.modules.identity.telegram import TelegramLoginVerifier


def _service(repository: IdentityRepository) -> IdentityService:
    return IdentityService(
        OtpSecurity("p" * 32),
        TokenSecurity("j" * 32),
        repository=repository,
        policy=IdentityPolicy(
            password_max_attempts=2,
            password_lockout=timedelta(minutes=5),
        ),
    )


def test_password_authentication_hashes_locks_and_unlocks() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        repository = IdentityRepository()
        service = _service(repository)
        now = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=6)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await repository.ensure_system_authorization(session)
            user = await repository.create_customer(
                session,
                email="password@example.test",
                email_normalized="password@example.test",
            )
            user.email_verified_at = now
            await service.set_password(
                session,
                user_id=user.id,
                new_password="correct horse battery staple",
                current_password=None,
                now=now,
            )
            user_id = user.id
            await session.commit()

        async with database.session() as session:
            credential = await repository.get_password_credential(
                session,
                user_id=user_id,
            )
            assert isinstance(credential, PasswordCredential)
            assert "correct horse" not in credential.password_hash
            assert credential.password_hash.startswith("$argon2id$")

        for second in (1, 2):
            with pytest.raises(InvalidCredentialsError):
                async with database.session() as session:
                    await service.authenticate_password(
                        session,
                        identifier="PASSWORD@example.test",
                        password="wrong password value",
                        now=now + timedelta(seconds=second),
                    )

        with pytest.raises(InvalidCredentialsError):
            async with database.session() as session:
                await service.authenticate_password(
                    session,
                    identifier="password@example.test",
                    password="correct horse battery staple",
                    now=now + timedelta(minutes=1),
                )

        async with database.session() as session:
            tokens = await service.authenticate_password(
                session,
                identifier="password@example.test",
                password="correct horse battery staple",
                now=now + timedelta(minutes=6),
            )
            await session.commit()
        assert tokens.user.id == user_id
        assert service.token_security.decode_access_token(tokens.access_token).user_id == user_id
        await database.shutdown()

    asyncio.run(scenario())


def _telegram_payload(bot_token: str, now: datetime) -> dict[str, str | int]:
    payload: dict[str, str | int] = {
        "id": 987654321,
        "auth_date": int(now.timestamp()),
        "first_name": "Nikita",
        "username": "nikita_test",
    }
    check = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret = hashlib.sha256(bot_token.encode()).digest()
    payload["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return payload


def test_telegram_signature_and_external_identity_are_verified_and_reused() -> None:
    async def scenario() -> None:
        bot_token = "123456:test-token"
        now = datetime.now(timezone.utc).replace(microsecond=0)
        verifier = TelegramLoginVerifier(bot_token, max_age=timedelta(minutes=10))
        payload = _telegram_payload(bot_token, now)
        principal = verifier.verify(payload, now=now)
        assert principal.provider == "telegram"
        assert principal.subject == "987654321"

        tampered = dict(payload)
        tampered["username"] = "attacker"
        with pytest.raises(InvalidExternalAuthPayloadError):
            verifier.verify(tampered, now=now)
        with pytest.raises(InvalidExternalAuthPayloadError, match="expired"):
            verifier.verify(payload, now=now + timedelta(minutes=11))

        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        repository = IdentityRepository()
        service = _service(repository)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await repository.ensure_system_authorization(session)
            first = await service.authenticate_external(session, principal=principal, now=now)
            await session.commit()
        async with database.session() as session:
            second = await service.authenticate_external(
                session,
                principal=principal,
                now=now + timedelta(seconds=1),
            )
            identity = await repository.get_external_identity(
                session,
                provider="telegram",
                subject=principal.subject,
            )
            await session.commit()
        assert first.user.id == second.user.id
        assert isinstance(identity, ExternalAuthIdentity)
        await database.shutdown()

    asyncio.run(scenario())


def test_auth_method_registry_exposes_disabled_provider_boundaries() -> None:
    methods = build_auth_method_registry(
        Settings(_env_file=None, app_env=AppEnvironment.TEST)
    ).descriptors()
    indexed = {method.code: method for method in methods}

    assert indexed["email"].enabled
    assert indexed["password"].enabled
    assert indexed["phone"].reason == "provider_not_configured"
    assert indexed["telegram"].reason == "disabled_by_configuration"

    enabled = build_auth_method_registry(
        Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            identity_telegram_auth_enabled=True,
            telegram_bot_token="123456:test-token",
        )
    )
    assert enabled.get("telegram").descriptor.enabled

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            identity_telegram_auth_enabled=True,
        )
    with pytest.raises(ValueError, match="must stay disabled"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            identity_phone_auth_enabled=True,
        )


def test_phone_normalizer_is_ready_without_enabling_a_provider() -> None:
    assert normalize_phone("8 (999) 123-45-67") == (
        "8 (999) 123-45-67",
        "+79991234567",
    )


def test_phone_otp_core_is_provider_ready_but_disabled_in_configuration() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        repository = IdentityRepository()
        service = _service(repository)
        method = PhoneOtpAuthMethod(enabled=True)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await repository.ensure_system_authorization(session)
            issued = await method.request_code(
                service,
                session,
                phone="8 (999) 123-45-67",
                now=now,
                client_ip="192.0.2.5",
                user_agent="provider contract",
            )
            await session.commit()
        async with database.session() as session:
            tokens = await method.verify_code(
                service,
                session,
                phone="+79991234567",
                code=issued.code,
                now=now + timedelta(seconds=1),
                client_ip="192.0.2.5",
                user_agent="provider contract",
            )
            await session.commit()
        assert tokens.user.phone_normalized == "+79991234567"
        assert tokens.user.phone_verified_at is not None
        await database.shutdown()

    asyncio.run(scenario())
