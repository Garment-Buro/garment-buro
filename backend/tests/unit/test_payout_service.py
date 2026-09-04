from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.models import User
from app.modules.payouts.models import Payout
from app.modules.payouts.provider import YooKassaPayoutProviderError
from app.modules.payouts.schemas import PayoutCreateCommand, YooKassaPayoutResponse
from app.modules.payouts.service import PayoutProviderFailedError, PayoutService

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
PROVIDER_KEY = "00000000-0000-4000-8000-000000000088"
PROVIDER_PAYOUT_ID = "po-" + "1" * 33


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        identity_api_enabled=True,
        identity_migration_fingerprint="a" * 64,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key="bm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm4=",
        yookassa_payout_agent_id="agent-id",
        yookassa_payout_api_key="payout-secret",
        yookassa_payouts_enabled=True,
    )


def _command() -> PayoutCreateCommand:
    return PayoutCreateCommand.model_validate(
        {
            "amount": {"value": "500.00", "currency": "RUB"},
            "destination": {"type": "payout_token", "token": "secret-payout-token"},
            "description": "Выплата по заказу 17",
            "reference": "order:17",
        }
    )


def _snapshot(*, status: str = "pending") -> YooKassaPayoutResponse:
    payload: dict[str, object] = {
        "id": PROVIDER_PAYOUT_ID,
        "amount": {"value": "500.00", "currency": "RUB"},
        "status": status,
        "payout_destination": {
            "type": "bank_card",
            "card": {"first6": "555555", "last4": "4477", "card_type": "MasterCard"},
        },
        "description": "Выплата по заказу 17",
        "created_at": "2026-09-04T12:00:00Z",
        "metadata": {"internal_payout_id": "1", "reference": "order:17"},
        "test": True,
    }
    if status == "succeeded":
        payload["succeeded_at"] = "2026-09-04T12:01:00Z"
    return YooKassaPayoutResponse.model_validate(payload)


@dataclass
class FakeProvider:
    outcomes: list[YooKassaPayoutResponse | Exception]
    calls: list[tuple[str, bytes]] = field(default_factory=list)
    get_calls: list[str] = field(default_factory=list)

    async def create_payout(
        self,
        *,
        idempotence_key: str,
        request_body: bytes,
    ) -> YooKassaPayoutResponse:
        self.calls.append((idempotence_key, request_body))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def get_payout(self, provider_payout_id: str) -> YooKassaPayoutResponse:
        self.get_calls.append(provider_payout_id)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def _seed_actor(database: DatabaseManager) -> int:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        actor = User(
            email="admin@example.test",
            email_normalized="admin@example.test",
            status="active",
        )
        session.add(actor)
        await session.commit()
        return actor.id


def test_payout_is_durable_idempotent_and_does_not_store_token(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "payout.db"))
        await database.startup()
        try:
            actor_id = await _seed_actor(database)
            provider = FakeProvider([_snapshot()])
            service = PayoutService(
                database.settings,
                provider,
                provider_key_factory=lambda: PROVIDER_KEY,
            )
            command = _command()
            assert "secret-payout-token" not in repr(command)
            async with database.session() as session:
                result = await service.create(
                    session,
                    command=command,
                    client_key="payout_creation_key_0001",
                    actor_user_id=actor_id,
                    now=NOW,
                )
            assert result.status == "pending"
            assert result.provider_payout_id == PROVIDER_PAYOUT_ID
            assert len(provider.calls) == 1
            provider_key, request_body = provider.calls[0]
            assert provider_key == PROVIDER_KEY
            assert json.loads(request_body)["payout_token"] == "secret-payout-token"

            async with database.session() as session:
                stored = await session.scalar(select(Payout))
                replay = await service.create(
                    session,
                    command=command,
                    client_key="payout_creation_key_0001",
                    actor_user_id=actor_id,
                    now=NOW + timedelta(minutes=1),
                )
            assert stored is not None
            assert "secret-payout-token" not in repr(stored)
            assert stored.requested_destination_type == "payout_token"
            assert replay.replayed
            assert len(provider.calls) == 1
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_payout_unknown_outcome_reuses_provider_idempotence_key(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "payout-retry.db"))
        await database.startup()
        try:
            actor_id = await _seed_actor(database)
            provider = FakeProvider(
                [
                    YooKassaPayoutProviderError(
                        "timeout",
                        retryable=True,
                        outcome_unknown=True,
                    ),
                    _snapshot(status="succeeded"),
                ]
            )
            service = PayoutService(
                database.settings,
                provider,
                provider_key_factory=lambda: PROVIDER_KEY,
            )
            async with database.session() as session:
                with pytest.raises(PayoutProviderFailedError) as first:
                    await service.create(
                        session,
                        command=_command(),
                        client_key="payout_creation_key_0002",
                        actor_user_id=actor_id,
                        now=NOW,
                    )
            assert first.value.outcome_unknown

            async with database.session() as session:
                result = await service.create(
                    session,
                    command=_command(),
                    client_key="payout_creation_key_0002",
                    actor_user_id=actor_id,
                    now=NOW + timedelta(seconds=61),
                )
                stored = await session.scalar(select(Payout))
            assert result.status == "succeeded"
            assert stored is not None and stored.attempts_count == 2
            assert [call[0] for call in provider.calls] == [PROVIDER_KEY, PROVIDER_KEY]
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_refresh_promotes_pending_payout_to_succeeded(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "payout-refresh.db"))
        await database.startup()
        try:
            actor_id = await _seed_actor(database)
            provider = FakeProvider([_snapshot(), _snapshot(status="succeeded")])
            service = PayoutService(
                database.settings,
                provider,
                provider_key_factory=lambda: PROVIDER_KEY,
            )
            async with database.session() as session:
                created = await service.create(
                    session,
                    command=_command(),
                    client_key="payout_creation_key_0003",
                    actor_user_id=actor_id,
                    now=NOW,
                )
            async with database.session() as session:
                refreshed = await service.refresh(
                    session,
                    payout_id=created.id,
                    now=NOW + timedelta(minutes=1),
                )
            assert refreshed.status == "succeeded"
            assert provider.get_calls == [PROVIDER_PAYOUT_ID]
        finally:
            await database.shutdown()

    asyncio.run(scenario())
