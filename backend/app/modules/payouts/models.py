from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class PayoutStatus(str, Enum):
    PREPARED = "prepared"
    UNKNOWN = "unknown"
    FAILED = "failed"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


class Payout(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "payouts"
    __table_args__ = (
        CheckConstraint("amount > 0", name="payout_amount_positive"),
        CheckConstraint("currency = 'RUB'", name="payout_currency_rub"),
        CheckConstraint(
            "requested_destination_type IN "
            "('payout_token', 'payment_method', 'bank_card', 'yoo_money', 'sbp')",
            name="payout_requested_destination_valid",
        ),
        CheckConstraint(
            "provider_destination_type IS NULL OR "
            "provider_destination_type IN ('bank_card', 'yoo_money', 'sbp')",
            name="payout_provider_destination_valid",
        ),
        CheckConstraint(
            "status IN ('prepared', 'unknown', 'failed', 'pending', 'succeeded', 'canceled')",
            name="payout_status_valid",
        ),
        CheckConstraint(
            "length(client_key_digest_sha256) = 64",
            name="payout_client_digest_length",
        ),
        CheckConstraint(
            "length(provider_idempotence_key) = 36",
            name="payout_provider_key_length",
        ),
        CheckConstraint(
            "request_sha256 IS NULL OR length(request_sha256) = 64",
            name="payout_request_digest_length",
        ),
        CheckConstraint("attempts_count >= 0", name="payout_attempts_nonnegative"),
        CheckConstraint(
            "(attempts_count = 0 AND last_attempt_at IS NULL) OR "
            "(attempts_count > 0 AND last_attempt_at IS NOT NULL)",
            name="payout_attempt_state_consistent",
        ),
        CheckConstraint(
            "(status IN ('failed', 'succeeded', 'canceled') AND resolved_at IS NOT NULL) OR "
            "(status NOT IN ('failed', 'succeeded', 'canceled') AND resolved_at IS NULL)",
            name="payout_resolution_consistent",
        ),
        CheckConstraint(
            "(status = 'canceled' AND cancellation_party IS NOT NULL "
            "AND cancellation_reason IS NOT NULL) OR "
            "(status <> 'canceled' AND cancellation_party IS NULL "
            "AND cancellation_reason IS NULL)",
            name="payout_cancellation_consistent",
        ),
    )

    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_key_digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provider_idempotence_key: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    request_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default="RUB",
    )
    description: Mapped[str] = mapped_column(String(128), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    requested_destination_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_destination_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PayoutStatus.PREPARED.value,
        server_default=PayoutStatus.PREPARED.value,
        index=True,
    )
    provider_payout_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
    )
    provider_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    attempts_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_party: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
