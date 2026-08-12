from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import (
    DeliveryAttemptStatus,
    NotificationDeliveryAttempt,
    NotificationOutbox,
    NotificationStatus,
)


class NotificationRepository:
    async def enqueue(
        self,
        session: AsyncSession,
        notification: NotificationOutbox,
    ) -> NotificationOutbox:
        values = {
            "channel": notification.channel,
            "template": notification.template,
            "payload_ciphertext": notification.payload_ciphertext,
            "payload_nonce": notification.payload_nonce,
            "payload_tag": notification.payload_tag,
            "encryption_key_version": notification.encryption_key_version,
            "deduplication_key": notification.deduplication_key,
            "status": notification.status or NotificationStatus.PENDING.value,
            "attempts_count": notification.attempts_count or 0,
            "max_attempts": notification.max_attempts,
            "available_at": notification.available_at,
            "discard_after": notification.discard_after,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(NotificationOutbox).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(NotificationOutbox).values(**values)
        else:
            raise RuntimeError("Notification outbox requires PostgreSQL or SQLite")
        await session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[NotificationOutbox.deduplication_key],
            )
        )
        stored = await session.scalar(
            select(NotificationOutbox)
            .where(NotificationOutbox.deduplication_key == notification.deduplication_key)
            .with_for_update()
        )
        if stored is None:
            raise RuntimeError("Notification outbox row could not be acquired")
        return stored

    async def claim_next(
        self,
        session: AsyncSession,
        *,
        now: datetime,
        stale_before: datetime,
        worker_id: str,
    ) -> tuple[NotificationOutbox, NotificationDeliveryAttempt] | None:
        notification = await session.scalar(
            select(NotificationOutbox)
            .where(
                or_(
                    (
                        NotificationOutbox.status.in_(
                            [
                                NotificationStatus.PENDING.value,
                                NotificationStatus.RETRY.value,
                            ]
                        )
                        & (NotificationOutbox.available_at <= now)
                    ),
                    (
                        (NotificationOutbox.status == NotificationStatus.PROCESSING.value)
                        & (NotificationOutbox.locked_at <= stale_before)
                    ),
                ),
                NotificationOutbox.attempts_count < NotificationOutbox.max_attempts,
            )
            .order_by(NotificationOutbox.available_at, NotificationOutbox.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if notification is None:
            return None

        if notification.status == NotificationStatus.PROCESSING.value:
            await self._abandon_processing_attempt(session, notification.id, now)

        notification.status = NotificationStatus.PROCESSING.value
        notification.attempts_count += 1
        notification.locked_at = now
        notification.locked_by = worker_id
        attempt = NotificationDeliveryAttempt(
            notification=notification,
            attempt_number=notification.attempts_count,
            status=DeliveryAttemptStatus.PROCESSING.value,
            started_at=now,
            worker_id=worker_id,
        )
        session.add(attempt)
        await session.flush()
        return notification, attempt

    @staticmethod
    async def cancel_pending(
        session: AsyncSession,
        *,
        deduplication_keys: list[str],
        now: datetime,
        error_code: str,
    ) -> int:
        if not deduplication_keys:
            return 0
        result = await session.execute(
            update(NotificationOutbox)
            .where(
                NotificationOutbox.deduplication_key.in_(deduplication_keys),
                NotificationOutbox.status.in_(
                    [
                        NotificationStatus.PENDING.value,
                        NotificationStatus.RETRY.value,
                    ]
                ),
            )
            .values(
                status=NotificationStatus.DEAD.value,
                payload_ciphertext=None,
                payload_nonce=None,
                payload_tag=None,
                locked_at=None,
                locked_by=None,
                last_error_code=error_code,
                last_error_at=now,
            )
        )
        return int(result.rowcount or 0)

    @staticmethod
    async def mark_sent(
        session: AsyncSession,
        notification: NotificationOutbox,
        attempt: NotificationDeliveryAttempt,
        *,
        now: datetime,
        provider_reference: str | None,
    ) -> None:
        notification.status = NotificationStatus.SENT.value
        notification.sent_at = now
        notification.locked_at = None
        notification.locked_by = None
        notification.last_error_code = None
        notification.last_error_at = None
        notification.payload_ciphertext = None
        notification.payload_nonce = None
        notification.payload_tag = None
        attempt.status = DeliveryAttemptStatus.SENT.value
        attempt.finished_at = now
        attempt.provider_reference = provider_reference
        await session.flush()

    @staticmethod
    async def mark_failed(
        session: AsyncSession,
        notification: NotificationOutbox,
        attempt: NotificationDeliveryAttempt,
        *,
        now: datetime,
        available_at: datetime,
        error_code: str,
        permanent: bool,
    ) -> None:
        terminal = permanent or notification.attempts_count >= notification.max_attempts
        notification.status = (
            NotificationStatus.DEAD.value if terminal else NotificationStatus.RETRY.value
        )
        notification.available_at = available_at
        notification.locked_at = None
        notification.locked_by = None
        notification.last_error_code = error_code
        notification.last_error_at = now
        attempt.status = (
            DeliveryAttemptStatus.DEAD.value if terminal else DeliveryAttemptStatus.RETRY.value
        )
        attempt.error_code = error_code
        attempt.finished_at = now
        if terminal:
            notification.payload_ciphertext = None
            notification.payload_nonce = None
            notification.payload_tag = None
        await session.flush()

    @staticmethod
    async def _abandon_processing_attempt(
        session: AsyncSession,
        notification_id: int,
        now: datetime,
    ) -> None:
        await session.execute(
            update(NotificationDeliveryAttempt)
            .where(
                NotificationDeliveryAttempt.notification_id == notification_id,
                NotificationDeliveryAttempt.status == DeliveryAttemptStatus.PROCESSING.value,
            )
            .values(
                status=DeliveryAttemptStatus.ABANDONED.value,
                finished_at=now,
                error_code="worker_stale",
            )
        )
