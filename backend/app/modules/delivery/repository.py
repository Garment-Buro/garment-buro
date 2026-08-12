from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.delivery.crypto import EncryptedCdekRequest
from app.modules.delivery.models import (
    CdekShipment,
    CdekShipmentAttempt,
    CdekShipmentAttemptStatus,
    CdekShipmentEvent,
    CdekShipmentEventType,
    CdekShipmentStatus,
)


class CdekShipmentEvidenceConflictError(RuntimeError):
    pass


class CdekShipmentRepository:
    async def acquire_prepared(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        source_fulfillment_job_id: int,
        source_payment_attempt_id: int,
        client_order_number: str,
        request_sha256: str,
        request_schema_version: int,
        encrypted: EncryptedCdekRequest,
        max_attempts: int,
        available_at: datetime,
    ) -> CdekShipment:
        values = {
            "order_id": order_id,
            "source_fulfillment_job_id": source_fulfillment_job_id,
            "source_payment_attempt_id": source_payment_attempt_id,
            "client_order_number": client_order_number,
            "request_sha256": request_sha256,
            "request_schema_version": request_schema_version,
            "request_ciphertext": encrypted.ciphertext,
            "request_nonce": encrypted.nonce,
            "request_tag": encrypted.tag,
            "encryption_key_version": encrypted.key_version,
            "status": CdekShipmentStatus.PENDING.value,
            "attempts_count": 0,
            "max_attempts": max_attempts,
            "available_at": available_at,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(CdekShipment).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(CdekShipment).values(**values)
        else:
            raise RuntimeError("CDEK shipment handoff requires PostgreSQL or SQLite")
        inserted_id = await session.scalar(
            statement.on_conflict_do_nothing(
                index_elements=[CdekShipment.order_id],
            ).returning(CdekShipment.id)
        )
        shipment = await session.scalar(
            select(CdekShipment).where(CdekShipment.order_id == order_id).with_for_update()
        )
        if shipment is None:
            raise RuntimeError("CDEK shipment could not be acquired")
        expected = (
            shipment.source_fulfillment_job_id == source_fulfillment_job_id
            and shipment.source_payment_attempt_id == source_payment_attempt_id
            and shipment.client_order_number == client_order_number
            and shipment.request_sha256 == request_sha256
            and shipment.request_schema_version == request_schema_version
        )
        if not expected:
            raise CdekShipmentEvidenceConflictError(
                "CDEK shipment is linked to different immutable evidence"
            )
        if inserted_id is not None:
            session.add(
                CdekShipmentEvent(
                    shipment_id=shipment.id,
                    event_key=f"prepared:{request_sha256}",
                    event_type=CdekShipmentEventType.PREPARED.value,
                    occurred_at=available_at,
                )
            )
        await session.flush()
        return shipment

    async def quarantine_stale_processing(
        self,
        session: AsyncSession,
        *,
        stale_before: datetime,
        now: datetime,
    ) -> CdekShipment | None:
        shipment = await session.scalar(
            select(CdekShipment)
            .where(
                CdekShipment.status == CdekShipmentStatus.PROCESSING.value,
                CdekShipment.locked_at <= stale_before,
            )
            .order_by(CdekShipment.locked_at, CdekShipment.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if shipment is None:
            return None
        attempt = await session.scalar(
            select(CdekShipmentAttempt)
            .where(
                CdekShipmentAttempt.shipment_id == shipment.id,
                CdekShipmentAttempt.attempt_number == shipment.attempts_count,
                CdekShipmentAttempt.status == CdekShipmentAttemptStatus.PROCESSING.value,
            )
            .with_for_update()
        )
        if attempt is None:
            raise RuntimeError("Stale CDEK shipment has no matching processing attempt")
        attempt.status = CdekShipmentAttemptStatus.UNKNOWN.value
        attempt.error_code = "processing_stale_unknown"
        attempt.completed_at = now
        shipment.status = CdekShipmentStatus.UNKNOWN.value
        shipment.locked_at = None
        shipment.locked_by = None
        shipment.last_error_code = "processing_stale_unknown"
        shipment.last_error_at = now
        session.add(
            CdekShipmentEvent(
                shipment_id=shipment.id,
                event_key=f"shipment:{shipment.id}:attempt:{attempt.attempt_number}:unknown",
                event_type=CdekShipmentEventType.CREATE_UNKNOWN.value,
                error_code="processing_stale_unknown",
                occurred_at=now,
            )
        )
        await session.flush()
        return shipment

    async def claim_next(
        self,
        session: AsyncSession,
        *,
        now: datetime,
        worker_id: str,
    ) -> tuple[CdekShipment, CdekShipmentAttempt] | None:
        shipment = await session.scalar(
            select(CdekShipment)
            .where(
                CdekShipment.status.in_(
                    (
                        CdekShipmentStatus.PENDING.value,
                        CdekShipmentStatus.RETRY.value,
                    )
                ),
                CdekShipment.available_at <= now,
                CdekShipment.attempts_count < CdekShipment.max_attempts,
            )
            .order_by(CdekShipment.available_at, CdekShipment.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if shipment is None:
            return None
        shipment.status = CdekShipmentStatus.PROCESSING.value
        shipment.attempts_count += 1
        shipment.locked_at = now
        shipment.locked_by = worker_id
        shipment.creation_started_at = shipment.creation_started_at or now
        shipment.creation_last_attempt_at = now
        shipment.last_error_code = None
        attempt = CdekShipmentAttempt(
            shipment_id=shipment.id,
            attempt_number=shipment.attempts_count,
            worker_id=worker_id,
            request_sha256=shipment.request_sha256,
            status=CdekShipmentAttemptStatus.PROCESSING.value,
            started_at=now,
        )
        session.add(attempt)
        session.add(
            CdekShipmentEvent(
                shipment_id=shipment.id,
                event_key=(
                    f"shipment:{shipment.id}:attempt:{shipment.attempts_count}:create-started"
                ),
                event_type=CdekShipmentEventType.CREATE_STARTED.value,
                occurred_at=now,
            )
        )
        await session.flush()
        return shipment, attempt

    async def get_owned_processing_for_update(
        self,
        session: AsyncSession,
        *,
        shipment_id: int,
        worker_id: str,
    ) -> tuple[CdekShipment, CdekShipmentAttempt] | None:
        shipment = await session.scalar(
            select(CdekShipment)
            .where(
                CdekShipment.id == shipment_id,
                CdekShipment.status == CdekShipmentStatus.PROCESSING.value,
                CdekShipment.locked_by == worker_id,
            )
            .with_for_update()
        )
        if shipment is None:
            return None
        attempt = await session.scalar(
            select(CdekShipmentAttempt)
            .where(
                CdekShipmentAttempt.shipment_id == shipment.id,
                CdekShipmentAttempt.attempt_number == shipment.attempts_count,
                CdekShipmentAttempt.status == CdekShipmentAttemptStatus.PROCESSING.value,
            )
            .with_for_update()
        )
        if attempt is None:
            raise RuntimeError("Owned CDEK shipment has no processing attempt")
        return shipment, attempt

    @staticmethod
    async def mark_created(
        session: AsyncSession,
        shipment: CdekShipment,
        attempt: CdekShipmentAttempt,
        *,
        provider_uuid: str,
        cdek_number: str | None,
        status_code: str | None,
        status_name: str | None,
        now: datetime,
    ) -> None:
        shipment.status = CdekShipmentStatus.CREATED.value
        shipment.provider_uuid = provider_uuid
        shipment.provider_cdek_number = cdek_number
        shipment.provider_status_code = status_code
        shipment.provider_status_name = status_name
        shipment.provider_status_observed_at = now if status_code is not None else None
        shipment.provider_created_at = now
        shipment.locked_at = None
        shipment.locked_by = None
        shipment.last_error_code = None
        shipment.last_error_at = None
        attempt.status = CdekShipmentAttemptStatus.CREATED.value
        attempt.provider_uuid = provider_uuid
        attempt.completed_at = now
        session.add(
            CdekShipmentEvent(
                shipment_id=shipment.id,
                event_key=f"shipment:{shipment.id}:attempt:{attempt.attempt_number}:created",
                event_type=CdekShipmentEventType.CREATED.value,
                provider_status_code=status_code,
                occurred_at=now,
            )
        )
        await session.flush()

    @staticmethod
    async def mark_unknown(
        session: AsyncSession,
        shipment: CdekShipment,
        attempt: CdekShipmentAttempt,
        *,
        error_code: str,
        provider_uuid: str | None,
        now: datetime,
    ) -> None:
        shipment.status = CdekShipmentStatus.UNKNOWN.value
        shipment.provider_uuid = provider_uuid or shipment.provider_uuid
        shipment.locked_at = None
        shipment.locked_by = None
        shipment.last_error_code = error_code
        shipment.last_error_at = now
        attempt.status = CdekShipmentAttemptStatus.UNKNOWN.value
        attempt.provider_uuid = provider_uuid
        attempt.error_code = error_code
        attempt.completed_at = now
        session.add(
            CdekShipmentEvent(
                shipment_id=shipment.id,
                event_key=f"shipment:{shipment.id}:attempt:{attempt.attempt_number}:unknown",
                event_type=CdekShipmentEventType.CREATE_UNKNOWN.value,
                error_code=error_code,
                occurred_at=now,
            )
        )
        await session.flush()

    @staticmethod
    async def mark_failed(
        session: AsyncSession,
        shipment: CdekShipment,
        attempt: CdekShipmentAttempt,
        *,
        available_at: datetime,
        error_code: str,
        permanent: bool,
        provider_uuid: str | None,
        now: datetime,
    ) -> None:
        exhausted = shipment.attempts_count >= shipment.max_attempts
        is_dead = permanent or exhausted
        shipment.status = (
            CdekShipmentStatus.DEAD.value if is_dead else CdekShipmentStatus.RETRY.value
        )
        shipment.available_at = available_at
        shipment.provider_uuid = provider_uuid or shipment.provider_uuid
        shipment.locked_at = None
        shipment.locked_by = None
        shipment.last_error_code = error_code
        shipment.last_error_at = now
        attempt.status = (
            CdekShipmentAttemptStatus.DEAD.value
            if is_dead
            else CdekShipmentAttemptStatus.RETRY.value
        )
        attempt.provider_uuid = provider_uuid
        attempt.error_code = error_code
        attempt.completed_at = now
        event_type = (
            CdekShipmentEventType.CREATE_DEAD.value
            if is_dead
            else CdekShipmentEventType.CREATE_RETRY.value
        )
        session.add(
            CdekShipmentEvent(
                shipment_id=shipment.id,
                event_key=(f"shipment:{shipment.id}:attempt:{attempt.attempt_number}:{event_type}"),
                event_type=event_type,
                error_code=error_code,
                occurred_at=now,
            )
        )
        await session.flush()
