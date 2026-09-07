from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class PartnerBankPayment(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "partner_bank_payments"
    __table_args__ = (
        CheckConstraint("provider = 'tochka'", name="bank_payment_provider_valid"),
        CheckConstraint(
            "environment IN ('sandbox', 'production')", name="bank_payment_environment_valid"
        ),
        CheckConstraint(
            "state IN ('submitting', 'unknown', 'awaiting_signature', 'processing', 'paid', 'rejected', 'canceled')",
            name="bank_payment_state_valid",
        ),
    )

    payout_id: Mapped[int] = mapped_column(
        ForeignKey("partner_payout_requests.id", ondelete="RESTRICT"), unique=True
    )
    provider: Mapped[str] = mapped_column(String(20), default="tochka", server_default="tochka")
    environment: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(24), index=True)
    request_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    signing_url: Mapped[str | None] = mapped_column(Text)
    provider_status: Mapped[str | None] = mapped_column(String(32))
    command_sha256: Mapped[str] = mapped_column(String(64))
    ciphertext: Mapped[str] = mapped_column(Text)
    nonce: Mapped[str] = mapped_column(String(64))
    tag: Mapped[str] = mapped_column(String(64))
    key_version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    last_error: Mapped[str | None] = mapped_column(String(64))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PartnerBankPaymentEvent(Base, IntegerIdMixin):
    __tablename__ = "partner_bank_payment_events"
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("partner_bank_payments.id", ondelete="RESTRICT"), index=True
    )
    state: Mapped[str] = mapped_column(String(24))
    provider_status: Mapped[str | None] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
