from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.security import ensure_utc
from app.modules.notifications.crypto import (
    EncryptedNotificationPayload,
    NotificationPayloadCodec,
    PayloadDecryptionError,
)
from app.modules.notifications.models import (
    NotificationChannel,
    NotificationDeliveryAttempt,
    NotificationOutbox,
    NotificationTemplate,
)
from app.modules.notifications.rendering import (
    InvalidNotificationPayloadError,
    NotificationRenderer,
    UnsupportedNotificationTemplateError,
)
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.transport import (
    EmailTransport,
    NotificationDeliveryError,
)


@dataclass(frozen=True, slots=True)
class NotificationPolicy:
    max_attempts: int = 5
    retry_base: timedelta = timedelta(seconds=60)
    retry_cap: timedelta = timedelta(hours=1)
    processing_timeout: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 20:
            raise ValueError("Notification max attempts must be between 1 and 20")
        if self.retry_base <= timedelta(0) or self.retry_cap < self.retry_base:
            raise ValueError("Notification retry durations are invalid")
        if self.processing_timeout <= timedelta(0):
            raise ValueError("Notification processing timeout must be positive")


@dataclass(frozen=True, slots=True)
class DispatchResult:
    notification_id: int
    status: str
    attempt_number: int
    error_code: str | None = None


class NotificationOutboxService:
    def __init__(
        self,
        codec: NotificationPayloadCodec,
        *,
        repository: NotificationRepository | None = None,
        policy: NotificationPolicy | None = None,
    ) -> None:
        self.codec = codec
        self.repository = repository or NotificationRepository()
        self.policy = policy or NotificationPolicy()

    async def enqueue_auth_otp(
        self,
        session: AsyncSession,
        *,
        recipient: str,
        code: str,
        purpose: str,
        expires_minutes: int,
        deduplication_key: str,
        now: datetime,
        discard_after: datetime | None = None,
    ) -> NotificationOutbox:
        encrypted = self.codec.encrypt(
            {
                "recipient": recipient,
                "code": code,
                "purpose": purpose,
                "expires_minutes": expires_minutes,
            }
        )
        notification = NotificationOutbox(
            channel=NotificationChannel.EMAIL.value,
            template=NotificationTemplate.AUTH_OTP.value,
            payload_ciphertext=encrypted.ciphertext,
            payload_nonce=encrypted.nonce,
            payload_tag=encrypted.tag,
            encryption_key_version=encrypted.key_version,
            deduplication_key=deduplication_key,
            max_attempts=self.policy.max_attempts,
            available_at=ensure_utc(now),
            discard_after=ensure_utc(discard_after) if discard_after is not None else None,
        )
        return await self.repository.enqueue(session, notification)

    async def cancel_auth_otp(
        self,
        session: AsyncSession,
        *,
        challenge_ids: list[int] | tuple[int, ...],
        now: datetime,
        reason: str,
    ) -> int:
        if reason not in {"challenge_replaced", "challenge_consumed"}:
            raise ValueError("Unsupported auth OTP cancellation reason")
        return await self.repository.cancel_pending(
            session,
            deduplication_keys=[
                f"otp:challenge:{challenge_id}"
                for challenge_id in challenge_ids
                if challenge_id > 0
            ],
            now=ensure_utc(now),
            error_code=reason,
        )

    async def enqueue_order_payment_confirmed(
        self,
        session: AsyncSession,
        *,
        recipient: str,
        order_id: int,
        first_name: str | None,
        items: list[dict[str, object]],
        items_subtotal: str,
        delivery_price: str,
        total_price: str,
        currency: str,
        now: datetime,
    ) -> NotificationOutbox:
        encrypted = self.codec.encrypt(
            {
                "recipient": recipient,
                "order_id": order_id,
                "first_name": first_name,
                "items": items,
                "items_subtotal": items_subtotal,
                "delivery_price": delivery_price,
                "total_price": total_price,
                "currency": currency,
            }
        )
        notification = NotificationOutbox(
            channel=NotificationChannel.EMAIL.value,
            template=NotificationTemplate.ORDER_PAYMENT_CONFIRMED.value,
            payload_ciphertext=encrypted.ciphertext,
            payload_nonce=encrypted.nonce,
            payload_tag=encrypted.tag,
            encryption_key_version=encrypted.key_version,
            deduplication_key=f"order:payment-confirmed:{order_id}",
            max_attempts=self.policy.max_attempts,
            available_at=ensure_utc(now),
            discard_after=None,
        )
        return await self.repository.enqueue(session, notification)


class NotificationDispatcher:
    def __init__(
        self,
        codec: NotificationPayloadCodec,
        transport: EmailTransport,
        *,
        repository: NotificationRepository | None = None,
        renderer: NotificationRenderer | None = None,
        policy: NotificationPolicy | None = None,
    ) -> None:
        self.codec = codec
        self.transport = transport
        self.repository = repository or NotificationRepository()
        self.renderer = renderer or NotificationRenderer()
        self.policy = policy or NotificationPolicy()

    async def dispatch_once(
        self,
        session: AsyncSession,
        *,
        now: datetime,
        worker_id: str,
    ) -> DispatchResult | None:
        now = ensure_utc(now)
        claimed = await self.repository.claim_next(
            session,
            now=now,
            stale_before=now - self.policy.processing_timeout,
            worker_id=worker_id,
        )
        if claimed is None:
            return None
        notification, attempt = claimed
        await session.commit()

        if notification.discard_after is not None and ensure_utc(notification.discard_after) <= now:
            return await self._fail(
                session,
                notification,
                attempt,
                now=now,
                error_code="notification_expired",
                permanent=True,
            )

        try:
            payload = self.codec.decrypt(
                EncryptedNotificationPayload(
                    ciphertext=notification.payload_ciphertext or "",
                    nonce=notification.payload_nonce or "",
                    tag=notification.payload_tag or "",
                    key_version=notification.encryption_key_version,
                )
            )
            message = self.renderer.render_email(notification.template, payload)
            provider_reference = await self.transport.send(message)
        except PayloadDecryptionError:
            return await self._fail(
                session,
                notification,
                attempt,
                now=now,
                error_code="payload_invalid",
                permanent=True,
            )
        except (InvalidNotificationPayloadError, UnsupportedNotificationTemplateError):
            return await self._fail(
                session,
                notification,
                attempt,
                now=now,
                error_code="template_invalid",
                permanent=True,
            )
        except NotificationDeliveryError:
            return await self._fail(
                session,
                notification,
                attempt,
                now=now,
                error_code="smtp_delivery",
                permanent=False,
            )
        except Exception:  # noqa: BLE001 - one bad delivery must not stop the worker
            return await self._fail(
                session,
                notification,
                attempt,
                now=now,
                error_code="unexpected_delivery",
                permanent=False,
            )

        await self.repository.mark_sent(
            session,
            notification,
            attempt,
            now=now,
            provider_reference=provider_reference,
        )
        await session.commit()
        return DispatchResult(
            notification_id=notification.id,
            status=notification.status,
            attempt_number=attempt.attempt_number,
        )

    async def _fail(
        self,
        session: AsyncSession,
        notification: NotificationOutbox,
        attempt: NotificationDeliveryAttempt,
        *,
        now: datetime,
        error_code: str,
        permanent: bool,
    ) -> DispatchResult:
        retry_delay = min(
            self.policy.retry_base * (2 ** max(0, notification.attempts_count - 1)),
            self.policy.retry_cap,
        )
        await self.repository.mark_failed(
            session,
            notification,
            attempt,
            now=now,
            available_at=now + retry_delay,
            error_code=error_code,
            permanent=permanent,
        )
        await session.commit()
        return DispatchResult(
            notification_id=notification.id,
            status=notification.status,
            attempt_number=attempt.attempt_number,
            error_code=error_code,
        )
