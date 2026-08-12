from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class CdekShipmentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    UNKNOWN = "unknown"
    RETRY = "retry"
    CREATED = "created"
    DEAD = "dead"


class CdekShipmentEventType(str, Enum):
    PREPARED = "prepared"
    CREATE_STARTED = "create_started"
    CREATE_UNKNOWN = "create_unknown"
    CREATE_RETRY = "create_retry"
    CREATED = "created"
    CREATE_DEAD = "create_dead"
    STATUS_OBSERVED = "status_observed"


class CdekShipmentAttemptStatus(str, Enum):
    PROCESSING = "processing"
    RETRY = "retry"
    UNKNOWN = "unknown"
    CREATED = "created"
    DEAD = "dead"


class CdekShipment(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "cdek_shipments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'unknown', 'retry', 'created', 'dead')",
            name="cdek_shipment_status_valid",
        ),
        CheckConstraint(
            "length(request_sha256) = 64",
            name="cdek_shipment_request_digest_length",
        ),
        CheckConstraint(
            "request_schema_version > 0 AND encryption_key_version > 0",
            name="cdek_shipment_versions_positive",
        ),
        CheckConstraint(
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name="cdek_shipment_attempts_valid",
        ),
        CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 20",
            name="cdek_shipment_max_attempts_valid",
        ),
        CheckConstraint(
            "(status = 'processing' AND locked_at IS NOT NULL AND locked_by IS NOT NULL) OR "
            "(status <> 'processing' AND locked_at IS NULL AND locked_by IS NULL)",
            name="cdek_shipment_lock_consistent",
        ),
        CheckConstraint(
            "(status = 'created' AND provider_uuid IS NOT NULL "
            "AND provider_created_at IS NOT NULL) OR "
            "(status <> 'created' AND provider_created_at IS NULL)",
            name="cdek_shipment_created_evidence_consistent",
        ),
        Index("ix_cdek_shipments_dispatch", "status", "available_at"),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    source_fulfillment_job_id: Mapped[int] = mapped_column(
        ForeignKey("fulfillment_jobs.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    source_payment_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    client_order_number: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    request_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    request_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    request_nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    request_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    encryption_key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CdekShipmentStatus.PENDING.value,
        server_default=CdekShipmentStatus.PENDING.value,
        index=True,
    )
    attempts_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    creation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    creation_last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    provider_uuid: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
    )
    provider_cdek_number: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
    )
    provider_status_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_status_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_status_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    provider_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list[CdekShipmentEvent]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CdekShipmentEvent.id",
    )
    attempts: Mapped[list[CdekShipmentAttempt]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CdekShipmentAttempt.attempt_number",
    )


class CdekShipmentAttempt(Base, IntegerIdMixin):
    __tablename__ = "cdek_shipment_attempts"
    __table_args__ = (
        UniqueConstraint(
            "shipment_id",
            "attempt_number",
            name="uq_cdek_shipment_attempt_number",
        ),
        CheckConstraint("attempt_number > 0", name="cdek_shipment_attempt_number_positive"),
        CheckConstraint(
            "status IN ('processing', 'retry', 'unknown', 'created', 'dead')",
            name="cdek_shipment_attempt_status_valid",
        ),
        CheckConstraint(
            "length(request_sha256) = 64",
            name="cdek_shipment_attempt_request_digest_length",
        ),
        CheckConstraint(
            "(status = 'processing' AND completed_at IS NULL) OR "
            "(status <> 'processing' AND completed_at IS NOT NULL)",
            name="cdek_shipment_attempt_completion_consistent",
        ),
    )

    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("cdek_shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    provider_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    shipment: Mapped[CdekShipment] = relationship(back_populates="attempts")


class CdekShipmentEvent(Base, IntegerIdMixin):
    __tablename__ = "cdek_shipment_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_cdek_shipment_event_key"),
        CheckConstraint(
            "event_type IN ('prepared', 'create_started', 'create_unknown', "
            "'create_retry', 'created', 'create_dead', 'status_observed')",
            name="cdek_shipment_event_type_valid",
        ),
    )

    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("cdek_shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider_status_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    shipment: Mapped[CdekShipment] = relationship(back_populates="events")
