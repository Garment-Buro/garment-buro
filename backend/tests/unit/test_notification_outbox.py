from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.core.exceptions import ConfigurationError
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.notifications.crypto import (
    EncryptedNotificationPayload,
    NotificationPayloadCodec,
    PayloadDecryptionError,
)
from app.modules.notifications.factory import build_notification_codec
from app.modules.notifications.models import (
    DeliveryAttemptStatus,
    NotificationChannel,
    NotificationDeliveryAttempt,
    NotificationOutbox,
    NotificationStatus,
)
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import (
    NotificationDispatcher,
    NotificationOutboxService,
    NotificationPolicy,
)
from app.modules.notifications.transport import (
    DisabledPhoneTransport,
    NotificationDeliveryError,
    NotificationTransportRegistry,
)


def encoded_key(byte: bytes = b"k") -> str:
    return base64.urlsafe_b64encode(byte * 32).decode("ascii").rstrip("=")


class FlakyEmailTransport:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        if len(self.messages) <= self.failures:
            raise NotificationDeliveryError("simulated SMTP failure")
        return f"provider-{len(self.messages)}"


class CaptureTelegramTransport:
    channel = NotificationChannel.TELEGRAM.value

    def __init__(self) -> None:
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        return "telegram-message-1"


def test_dispatcher_routes_telegram_and_disables_phone_permanently() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        codec = NotificationPayloadCodec.from_base64_key(encoded_key(b"m"))
        outbox = NotificationOutboxService(codec)
        telegram = CaptureTelegramTransport()
        dispatcher = NotificationDispatcher(
            codec,
            NotificationTransportRegistry([telegram, DisabledPhoneTransport()]),
        )
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with database.session() as session:
            await outbox.enqueue_auth_otp(
                session,
                recipient="987654321",
                code="1234",
                purpose="login",
                expires_minutes=10,
                deduplication_key="telegram:otp:1",
                now=now,
                channel=NotificationChannel.TELEGRAM,
            )
            await session.commit()
        async with database.session() as session:
            sent = await dispatcher.dispatch_once(session, now=now, worker_id="worker-tg")
        assert sent is not None
        assert sent.status == NotificationStatus.SENT.value
        assert "1234" in telegram.messages[0].text

        async with database.session() as session:
            await outbox.enqueue_auth_otp(
                session,
                recipient="+79991234567",
                code="5678",
                purpose="login",
                expires_minutes=10,
                deduplication_key="phone:otp:1",
                now=now + timedelta(seconds=1),
                channel=NotificationChannel.PHONE,
            )
            await session.commit()
        async with database.session() as session:
            failed = await dispatcher.dispatch_once(
                session,
                now=now + timedelta(seconds=1),
                worker_id="worker-phone",
            )
        assert failed is not None
        assert failed.status == NotificationStatus.DEAD.value
        assert failed.error_code == "channel_unavailable"
        await database.shutdown()

    asyncio.run(scenario())


def test_notification_payload_is_authenticated_and_not_plaintext() -> None:
    codec = NotificationPayloadCodec.from_base64_key(encoded_key(), key_version=3)
    source = {
        "recipient": "private@example.test",
        "code": "1234",
        "purpose": "login",
        "expires_minutes": 10,
    }

    encrypted = codec.encrypt(source)

    assert encrypted.key_version == 3
    assert "private@example.test" not in encrypted.ciphertext
    assert "1234" not in encrypted.ciphertext
    assert codec.decrypt(encrypted) == source

    replacement = "B" if encrypted.ciphertext.startswith("A") else "A"
    tampered = EncryptedNotificationPayload(
        ciphertext=f"{replacement}{encrypted.ciphertext[1:]}",
        nonce=encrypted.nonce,
        tag=encrypted.tag,
        key_version=encrypted.key_version,
    )
    with pytest.raises(PayloadDecryptionError):
        codec.decrypt(tampered)


def test_notification_codec_factory_requires_a_valid_32_byte_key() -> None:
    missing = Settings(_env_file=None, app_env=AppEnvironment.TEST)
    with pytest.raises(ConfigurationError, match="NOTIFICATION_ENCRYPTION_KEY"):
        build_notification_codec(missing)

    invalid = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        notification_encryption_key=base64.urlsafe_b64encode(b"short").decode(),
    )
    with pytest.raises(ValueError, match="32 bytes"):
        build_notification_codec(invalid)

    invalid_alphabet = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        notification_encryption_key=f"{encoded_key()[:-1]}!",
    )
    with pytest.raises(ValueError, match="URL-safe base64"):
        build_notification_codec(invalid_alphabet)

    with pytest.raises(ValueError, match="version must be positive"):
        NotificationPayloadCodec.from_base64_keys(
            {-1: encoded_key(b"o"), 1: encoded_key()},
            current_version=1,
        )

    configured = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        notification_encryption_key=encoded_key(),
        notification_encryption_key_version=4,
    )
    assert build_notification_codec(configured).current_version == 4

    rotated = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        notification_encryption_key=encoded_key(b"n"),
        notification_encryption_key_version=2,
        notification_previous_encryption_keys=('{"1":"' + encoded_key(b"o") + '"}'),
    )
    old_codec = NotificationPayloadCodec.from_base64_key(encoded_key(b"o"))
    old_payload = old_codec.encrypt({"probe": "old-key"})
    assert build_notification_codec(rotated).decrypt(old_payload) == {"probe": "old-key"}


def test_outbox_deduplicates_retries_and_erases_sent_payload() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        codec = NotificationPayloadCodec.from_base64_key(encoded_key())
        policy = NotificationPolicy(
            max_attempts=3,
            retry_base=timedelta(seconds=10),
            retry_cap=timedelta(minutes=1),
            processing_timeout=timedelta(minutes=5),
        )
        outbox_service = NotificationOutboxService(codec, policy=policy)
        transport = FlakyEmailTransport(failures=1)
        dispatcher = NotificationDispatcher(codec, transport, policy=policy)
        now = datetime.now(timezone.utc).replace(microsecond=0)

        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with database.session() as session:
            first = await outbox_service.enqueue_auth_otp(
                session,
                recipient="private@example.test",
                code="1234",
                purpose="login",
                expires_minutes=10,
                deduplication_key="otp:challenge:7",
                now=now,
            )
            duplicate = await outbox_service.enqueue_auth_otp(
                session,
                recipient="private@example.test",
                code="1234",
                purpose="login",
                expires_minutes=10,
                deduplication_key="otp:challenge:7",
                now=now,
            )
            await session.commit()
        assert first.id == duplicate.id

        async with database.session() as session:
            stored = await session.scalar(select(NotificationOutbox))
        assert stored is not None
        persisted_values = "|".join(
            str(value)
            for value in (
                stored.payload_ciphertext,
                stored.payload_nonce,
                stored.payload_tag,
                stored.deduplication_key,
            )
        )
        assert "private@example.test" not in persisted_values
        assert "1234" not in persisted_values

        async with database.session() as session:
            failed = await dispatcher.dispatch_once(
                session,
                now=now,
                worker_id="worker-a",
            )
        assert failed is not None
        assert failed.status == NotificationStatus.RETRY.value
        assert failed.error_code == "smtp_delivery"

        async with database.session() as session:
            unavailable = await dispatcher.dispatch_once(
                session,
                now=now + timedelta(seconds=9),
                worker_id="worker-a",
            )
        assert unavailable is None

        async with database.session() as session:
            sent = await dispatcher.dispatch_once(
                session,
                now=now + timedelta(seconds=10),
                worker_id="worker-a",
            )
        assert sent is not None
        assert sent.status == NotificationStatus.SENT.value
        assert sent.attempt_number == 2
        assert len(transport.messages) == 2
        assert "1234" in transport.messages[-1].html

        async with database.session() as session:
            stored = await session.scalar(select(NotificationOutbox))
            attempts = list(
                await session.scalars(
                    select(NotificationDeliveryAttempt).order_by(
                        NotificationDeliveryAttempt.attempt_number
                    )
                )
            )
        assert stored is not None
        assert stored.payload_ciphertext is None
        assert stored.payload_nonce is None
        assert stored.payload_tag is None
        assert stored.last_error_code is None
        assert [attempt.status for attempt in attempts] == [
            DeliveryAttemptStatus.RETRY.value,
            DeliveryAttemptStatus.SENT.value,
        ]
        assert attempts[-1].provider_reference == "provider-2"
        await database.shutdown()

    asyncio.run(scenario())


def test_stale_claim_is_abandoned_and_recovered() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        codec = NotificationPayloadCodec.from_base64_key(encoded_key(b"s"))
        policy = NotificationPolicy(max_attempts=3)
        repository = NotificationRepository()
        outbox_service = NotificationOutboxService(
            codec,
            repository=repository,
            policy=policy,
        )
        dispatcher = NotificationDispatcher(
            codec,
            FlakyEmailTransport(),
            repository=repository,
            policy=policy,
        )
        now = datetime.now(timezone.utc).replace(microsecond=0)

        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await outbox_service.enqueue_auth_otp(
                session,
                recipient="stale@example.test",
                code="5678",
                purpose="email_change",
                expires_minutes=10,
                deduplication_key="otp:challenge:8",
                now=now,
            )
            await session.commit()
        async with database.session() as session:
            claimed = await repository.claim_next(
                session,
                now=now,
                stale_before=now - timedelta(minutes=5),
                worker_id="dead-worker",
            )
            assert claimed is not None
            await session.commit()

        async with database.session() as session:
            recovered = await dispatcher.dispatch_once(
                session,
                now=now + timedelta(minutes=6),
                worker_id="healthy-worker",
            )
        assert recovered is not None
        assert recovered.status == NotificationStatus.SENT.value
        assert recovered.attempt_number == 2

        async with database.session() as session:
            attempts = list(
                await session.scalars(
                    select(NotificationDeliveryAttempt).order_by(
                        NotificationDeliveryAttempt.attempt_number
                    )
                )
            )
        assert [attempt.status for attempt in attempts] == [
            DeliveryAttemptStatus.ABANDONED.value,
            DeliveryAttemptStatus.SENT.value,
        ]
        assert attempts[0].error_code == "worker_stale"
        await database.shutdown()

    asyncio.run(scenario())


def test_tampered_payload_is_dead_lettered_without_retry() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        codec = NotificationPayloadCodec.from_base64_key(encoded_key(b"t"))
        service = NotificationOutboxService(codec)
        dispatcher = NotificationDispatcher(codec, FlakyEmailTransport())
        now = datetime.now(timezone.utc).replace(microsecond=0)

        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            notification = await service.enqueue_auth_otp(
                session,
                recipient="tampered@example.test",
                code="9876",
                purpose="login",
                expires_minutes=10,
                deduplication_key="otp:challenge:tampered",
                now=now,
            )
            assert notification.payload_tag is not None
            replacement = "B" if notification.payload_tag.startswith("A") else "A"
            notification.payload_tag = f"{replacement}{notification.payload_tag[1:]}"
            await session.commit()

        async with database.session() as session:
            result = await dispatcher.dispatch_once(
                session,
                now=now,
                worker_id="worker-tamper",
            )
        assert result is not None
        assert result.status == NotificationStatus.DEAD.value
        assert result.error_code == "payload_invalid"

        async with database.session() as session:
            stored = await session.scalar(select(NotificationOutbox))
            attempt = await session.scalar(select(NotificationDeliveryAttempt))
        assert stored is not None
        assert stored.payload_ciphertext is None
        assert stored.payload_nonce is None
        assert stored.payload_tag is None
        assert attempt is not None
        assert attempt.status == DeliveryAttemptStatus.DEAD.value
        await database.shutdown()

    asyncio.run(scenario())


def test_replaced_and_expired_otp_notifications_are_never_delivered() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        codec = NotificationPayloadCodec.from_base64_key(encoded_key(b"e"))
        service = NotificationOutboxService(codec)
        transport = FlakyEmailTransport()
        dispatcher = NotificationDispatcher(codec, transport)
        now = datetime.now(timezone.utc).replace(microsecond=0)

        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await service.enqueue_auth_otp(
                session,
                recipient="replaced@example.test",
                code="1111",
                purpose="login",
                expires_minutes=10,
                deduplication_key="otp:challenge:101",
                now=now,
                discard_after=now + timedelta(minutes=10),
            )
            cancelled = await service.cancel_auth_otp(
                session,
                challenge_ids=[101],
                now=now + timedelta(seconds=1),
                reason="challenge_replaced",
            )
            await service.enqueue_auth_otp(
                session,
                recipient="expired@example.test",
                code="2222",
                purpose="login",
                expires_minutes=10,
                deduplication_key="otp:challenge:102",
                now=now,
                discard_after=now + timedelta(seconds=5),
            )
            await session.commit()
        assert cancelled == 1

        async with database.session() as session:
            result = await dispatcher.dispatch_once(
                session,
                now=now + timedelta(seconds=6),
                worker_id="worker-expired",
            )
        assert result is not None
        assert result.status == NotificationStatus.DEAD.value
        assert result.error_code == "notification_expired"
        assert transport.messages == []

        async with database.session() as session:
            rows = list(
                await session.scalars(select(NotificationOutbox).order_by(NotificationOutbox.id))
            )
        assert [row.status for row in rows] == [
            NotificationStatus.DEAD.value,
            NotificationStatus.DEAD.value,
        ]
        assert [row.last_error_code for row in rows] == [
            "challenge_replaced",
            "notification_expired",
        ]
        assert all(row.payload_ciphertext is None for row in rows)
        await database.shutdown()

    asyncio.run(scenario())
