from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class PaymentProvider(str, Enum):
    YOOKASSA = "yookassa"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


class PaymentAttemptStatus(str, Enum):
    PREPARED = "prepared"
    UNKNOWN = "unknown"
    FAILED = "failed"
    PENDING = "pending"
    WAITING_FOR_CAPTURE = "waiting_for_capture"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


class PaymentEventStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    RETRY = "retry"
    PROCESSED = "processed"
    REJECTED = "rejected"
    DEAD = "dead"


class PaymentReconciliationStatus(str, Enum):
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    RETRY = "retry"
    COMPLETED = "completed"
    DEAD = "dead"


class Payment(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payments_order_id"),
        CheckConstraint("provider IN ('yookassa')", name="payment_provider_valid"),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'canceled')",
            name="payment_status_valid",
        ),
        CheckConstraint("amount > 0", name="payment_amount_positive"),
        CheckConstraint("currency = 'RUB'", name="payment_currency_rub"),
        CheckConstraint(
            "(status = 'succeeded' AND succeeded_at IS NOT NULL) OR "
            "(status <> 'succeeded' AND succeeded_at IS NULL)",
            name="payment_success_timestamp_consistent",
        ),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PaymentProvider.YOOKASSA.value,
        server_default=PaymentProvider.YOOKASSA.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PaymentStatus.PENDING.value,
        server_default=PaymentStatus.PENDING.value,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default="RUB",
    )
    succeeded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    attempts: Mapped[list[PaymentAttempt]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PaymentAttempt.attempt_number",
    )


class PaymentAttempt(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "payment_attempts"
    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            "attempt_number",
            name="uq_payment_attempt_number",
        ),
        UniqueConstraint(
            "client_key_digest_sha256",
            name="uq_payment_attempt_client_key_digest",
        ),
        UniqueConstraint(
            "provider_idempotence_key",
            name="uq_payment_attempt_provider_idempotence_key",
        ),
        UniqueConstraint(
            "provider_payment_id",
            name="uq_payment_attempt_provider_payment_id",
        ),
        CheckConstraint("attempt_number > 0", name="payment_attempt_number_positive"),
        CheckConstraint(
            "status IN ('prepared', 'unknown', 'failed', 'pending', 'waiting_for_capture', "
            "'succeeded', 'canceled')",
            name="payment_attempt_status_valid",
        ),
        CheckConstraint(
            "payment_method IN ('bank_card', 'sbp')",
            name="payment_attempt_method_valid",
        ),
        CheckConstraint(
            "length(client_key_digest_sha256) = 64",
            name="payment_attempt_client_digest_length",
        ),
        CheckConstraint(
            "length(request_fingerprint_sha256) = 64",
            name="payment_attempt_fingerprint_length",
        ),
        CheckConstraint(
            "length(provider_idempotence_key) = 36",
            name="payment_attempt_provider_key_length",
        ),
        CheckConstraint(
            "provider_payment_id IS NOT NULL OR status IN ('prepared', 'unknown', 'failed')",
            name="payment_attempt_provider_id_present",
        ),
        CheckConstraint(
            "(status IN ('failed', 'succeeded', 'canceled') AND resolved_at IS NOT NULL "
            "AND resolved_at >= created_at) OR "
            "(status NOT IN ('failed', 'succeeded', 'canceled') AND resolved_at IS NULL)",
            name="payment_attempt_resolution_after_creation",
        ),
        CheckConstraint(
            "(status = 'canceled' AND cancellation_party IS NOT NULL "
            "AND cancellation_reason IS NOT NULL) OR "
            "(status <> 'canceled' AND cancellation_party IS NULL "
            "AND cancellation_reason IS NULL)",
            name="payment_attempt_cancellation_consistent",
        ),
        CheckConstraint(
            "(provider_request_sha256 IS NULL AND creation_started_at IS NULL "
            "AND creation_last_attempt_at IS NULL AND creation_attempts_count = 0) OR "
            "(length(provider_request_sha256) = 64 AND creation_started_at IS NOT NULL "
            "AND creation_last_attempt_at IS NOT NULL AND creation_attempts_count > 0 "
            "AND creation_last_attempt_at >= creation_started_at)",
            name="payment_attempt_creation_consistent",
        ),
    )

    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    client_key_digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_idempotence_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PaymentAttemptStatus.PREPARED.value,
        server_default=PaymentAttemptStatus.PREPARED.value,
        index=True,
    )
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_request_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    creation_last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    creation_attempts_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    confirmation_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_party: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    payment: Mapped[Payment] = relationship(back_populates="attempts")
    events: Mapped[list[PaymentEvent]] = relationship(
        back_populates="attempt",
        passive_deletes=True,
        order_by="PaymentEvent.id",
    )
    reconciliation_job: Mapped[PaymentReconciliationJob | None] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class PaymentEvent(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("event_key_sha256", name="uq_payment_event_key"),
        CheckConstraint(
            "length(event_key_sha256) = 64",
            name="payment_event_key_length",
        ),
        CheckConstraint(
            "length(payload_sha256) = 64",
            name="payment_event_payload_digest_length",
        ),
        CheckConstraint(
            "length(observation_sha256) = 64",
            name="payment_event_observation_digest_length",
        ),
        CheckConstraint(
            "event_type IN ('payment.waiting_for_capture', 'payment.succeeded', "
            "'payment.canceled')",
            name="payment_event_type_valid",
        ),
        CheckConstraint(
            "observed_status IN ('waiting_for_capture', 'succeeded', 'canceled')",
            name="payment_event_observed_status_valid",
        ),
        CheckConstraint(
            "status IN ('received', 'processing', 'retry', 'processed', 'rejected', 'dead')",
            name="payment_event_status_valid",
        ),
        CheckConstraint("observed_amount > 0", name="payment_event_amount_positive"),
        CheckConstraint("observed_currency = 'RUB'", name="payment_event_currency_rub"),
        CheckConstraint("metadata_order_id > 0", name="payment_event_order_positive"),
        CheckConstraint(
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name="payment_event_attempts_valid",
        ),
        CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 20",
            name="payment_event_max_attempts_valid",
        ),
        CheckConstraint(
            "(status = 'processing' AND locked_at IS NOT NULL AND locked_by IS NOT NULL) OR "
            "(status <> 'processing' AND locked_at IS NULL AND locked_by IS NULL)",
            name="payment_event_lock_consistent",
        ),
        CheckConstraint(
            "(status = 'processed' AND processed_at IS NOT NULL) OR "
            "(status <> 'processed' AND processed_at IS NULL)",
            name="payment_event_processed_at_consistent",
        ),
        Index("ix_payment_events_dispatch", "status", "available_at"),
    )

    payment_attempt_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    event_key_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    observed_status: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    observed_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    observed_paid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_test: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metadata_order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    provider_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_party: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PaymentEventStatus.RECEIVED.value,
        server_default=PaymentEventStatus.RECEIVED.value,
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
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    attempt: Mapped[PaymentAttempt | None] = relationship(back_populates="events")


class PaymentReconciliationJob(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "payment_reconciliation_jobs"
    __table_args__ = (
        UniqueConstraint(
            "payment_attempt_id",
            name="uq_payment_reconciliation_job_attempt",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'processing', 'retry', 'completed', 'dead')",
            name="payment_reconciliation_status_valid",
        ),
        CheckConstraint(
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name="payment_reconciliation_attempts_valid",
        ),
        CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 1000",
            name="payment_reconciliation_max_attempts_valid",
        ),
        CheckConstraint(
            "(status = 'processing' AND locked_at IS NOT NULL AND locked_by IS NOT NULL) OR "
            "(status <> 'processing' AND locked_at IS NULL AND locked_by IS NULL)",
            name="payment_reconciliation_lock_consistent",
        ),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name="payment_reconciliation_completed_at_consistent",
        ),
        CheckConstraint(
            "(last_observation_sha256 IS NULL AND last_observed_status IS NULL) OR "
            "(length(last_observation_sha256) = 64 AND last_observed_status IN "
            "('pending', 'waiting_for_capture', 'succeeded', 'canceled'))",
            name="payment_reconciliation_observation_consistent",
        ),
        Index("ix_payment_reconciliation_dispatch", "status", "available_at"),
    )

    payment_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PaymentReconciliationStatus.SCHEDULED.value,
        server_default=PaymentReconciliationStatus.SCHEDULED.value,
        index=True,
    )
    attempts_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=288)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_observation_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_observed_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    attempt: Mapped[PaymentAttempt] = relationship(back_populates="reconciliation_job")
