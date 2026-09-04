from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class NotificationChannel(str, Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    PHONE = "phone"


class NotificationTemplate(str, Enum):
    AUTH_OTP = "auth_otp"
    ORDER_PAYMENT_CONFIRMED = "order_payment_confirmed"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRY = "retry"
    SENT = "sent"
    DEAD = "dead"


class DeliveryAttemptStatus(str, Enum):
    PROCESSING = "processing"
    RETRY = "retry"
    SENT = "sent"
    DEAD = "dead"
    ABANDONED = "abandoned"


class NotificationOutbox(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        UniqueConstraint(
            "deduplication_key",
            name="uq_notification_outbox_deduplication_key",
        ),
        CheckConstraint(
            "channel IN ('email', 'telegram', 'phone')",
            name="notification_outbox_channel_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'retry', 'sent', 'dead')",
            name="notification_outbox_status_valid",
        ),
        CheckConstraint(
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name="notification_outbox_attempts_valid",
        ),
        CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 20",
            name="notification_outbox_max_attempts_valid",
        ),
        CheckConstraint(
            "encryption_key_version > 0",
            name="notification_outbox_key_version_positive",
        ),
        CheckConstraint(
            "status IN ('sent', 'dead') OR "
            "(payload_ciphertext IS NOT NULL AND payload_nonce IS NOT NULL "
            "AND payload_tag IS NOT NULL)",
            name="notification_outbox_active_payload_present",
        ),
    )

    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    template: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_nonce: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload_tag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    encryption_key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=NotificationStatus.PENDING.value,
        server_default=NotificationStatus.PENDING.value,
        index=True,
    )
    attempts_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    discard_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    attempts: Mapped[list[NotificationDeliveryAttempt]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NotificationDeliveryAttempt.attempt_number",
    )


class NotificationDeliveryAttempt(Base, IntegerIdMixin):
    __tablename__ = "notification_delivery_attempts"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "attempt_number",
            name="uq_notification_delivery_attempt_number",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="notification_attempt_number_positive",
        ),
        CheckConstraint(
            "status IN ('processing', 'retry', 'sent', 'dead', 'abandoned')",
            name="notification_attempt_status_valid",
        ),
    )

    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notification_outbox.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)

    notification: Mapped[NotificationOutbox] = relationship(back_populates="attempts")
