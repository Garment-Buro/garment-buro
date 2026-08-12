from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.delivery.crypto import (
    CdekRequestCodec,
    CdekRequestDecryptionError,
    EncryptedCdekRequest,
)
from app.modules.delivery.models import CdekShipment, CdekShipmentAttempt, CdekShipmentStatus
from app.modules.delivery.provider import CdekOrderSnapshot, CdekProvider, CdekProviderError
from app.modules.delivery.repository import CdekShipmentRepository
from app.modules.identity.security import ensure_utc


@dataclass(frozen=True, slots=True)
class CdekWorkerPolicy:
    retry_base: timedelta = timedelta(seconds=30)
    retry_cap: timedelta = timedelta(minutes=30)
    processing_timeout: timedelta = timedelta(minutes=2)

    def __post_init__(self) -> None:
        if self.retry_base <= timedelta(0) or self.retry_cap < self.retry_base:
            raise ValueError("CDEK retry durations are invalid")
        if self.processing_timeout <= timedelta(0):
            raise ValueError("CDEK processing timeout must be positive")

    @classmethod
    def from_settings(cls, settings: Settings) -> CdekWorkerPolicy:
        return cls(
            retry_base=timedelta(seconds=settings.cdek_retry_base_seconds),
            retry_cap=timedelta(seconds=settings.cdek_retry_cap_seconds),
            processing_timeout=timedelta(seconds=settings.cdek_processing_timeout_seconds),
        )


@dataclass(frozen=True, slots=True)
class CdekProcessingResult:
    shipment_id: int
    status: str
    attempt_number: int
    provider_uuid: str | None = None
    error_code: str | None = None


class CdekShipmentOwnershipError(RuntimeError):
    pass


class CdekCreationDisabledError(RuntimeError):
    pass


class CdekShipmentProcessor:
    """Commit attempt evidence before CDEK I/O and quarantine ambiguous outcomes."""

    def __init__(
        self,
        settings: Settings,
        provider: CdekProvider,
        codec: CdekRequestCodec,
        *,
        repository: CdekShipmentRepository | None = None,
        policy: CdekWorkerPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.codec = codec
        self.repository = repository or CdekShipmentRepository()
        self.policy = policy or CdekWorkerPolicy.from_settings(settings)

    async def process_once(
        self,
        session: AsyncSession,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> CdekProcessingResult | None:
        if not self.settings.cdek_creation_enabled:
            raise CdekCreationDisabledError("Target CDEK creation is disabled")
        if not worker_id or len(worker_id) > 128:
            raise ValueError("CDEK worker ID must contain 1-128 characters")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        stale = await self.repository.quarantine_stale_processing(
            session,
            stale_before=current_time - self.policy.processing_timeout,
            now=current_time,
        )
        if stale is not None:
            await session.commit()
            return self._result(stale)

        claimed = await self.repository.claim_next(
            session,
            now=current_time,
            worker_id=worker_id,
        )
        if claimed is None:
            return None
        shipment, _attempt = claimed
        shipment_id = shipment.id
        encrypted = EncryptedCdekRequest(
            ciphertext=shipment.request_ciphertext,
            nonce=shipment.request_nonce,
            tag=shipment.request_tag,
            key_version=shipment.encryption_key_version,
        )
        order_id = shipment.order_id
        request_sha256 = shipment.request_sha256
        schema_version = shipment.request_schema_version
        client_order_number = shipment.client_order_number
        await session.commit()

        try:
            request_body = self.codec.decrypt(
                encrypted,
                order_id=order_id,
                request_sha256=request_sha256,
                schema_version=schema_version,
            )
        except CdekRequestDecryptionError:
            return await self._fail(
                session,
                shipment_id=shipment_id,
                worker_id=worker_id,
                now=current_time,
                error_code="request_decryption_failed",
                permanent=True,
            )

        try:
            snapshot = await self.provider.create_order(request_body)
        except CdekProviderError as error:
            if error.outcome_unknown:
                return await self._unknown(
                    session,
                    shipment_id=shipment_id,
                    worker_id=worker_id,
                    now=current_time,
                    error_code=error.code,
                    provider_uuid=error.provider_uuid,
                )
            return await self._fail(
                session,
                shipment_id=shipment_id,
                worker_id=worker_id,
                now=current_time,
                error_code=error.code,
                permanent=not error.retryable,
                provider_uuid=error.provider_uuid,
            )
        except Exception:  # noqa: BLE001 - a provider defect may follow an accepted POST
            return await self._unknown(
                session,
                shipment_id=shipment_id,
                worker_id=worker_id,
                now=current_time,
                error_code="provider_unexpected",
            )

        if (
            snapshot.client_order_number is not None
            and snapshot.client_order_number != client_order_number
        ):
            return await self._unknown(
                session,
                shipment_id=shipment_id,
                worker_id=worker_id,
                now=current_time,
                error_code="provider_order_number_mismatch",
                provider_uuid=snapshot.provider_uuid,
            )
        return await self._created(
            session,
            shipment_id=shipment_id,
            worker_id=worker_id,
            now=current_time,
            snapshot=snapshot,
        )

    async def _created(
        self,
        session: AsyncSession,
        *,
        shipment_id: int,
        worker_id: str,
        now: datetime,
        snapshot: CdekOrderSnapshot,
    ) -> CdekProcessingResult:
        shipment, attempt = await self._owned(
            session,
            shipment_id=shipment_id,
            worker_id=worker_id,
        )
        await self.repository.mark_created(
            session,
            shipment,
            attempt,
            provider_uuid=snapshot.provider_uuid,
            cdek_number=snapshot.cdek_number,
            status_code=snapshot.status_code,
            status_name=snapshot.status_name,
            now=now,
        )
        await session.commit()
        return self._result(shipment)

    async def _unknown(
        self,
        session: AsyncSession,
        *,
        shipment_id: int,
        worker_id: str,
        now: datetime,
        error_code: str,
        provider_uuid: str | None = None,
    ) -> CdekProcessingResult:
        shipment, attempt = await self._owned(
            session,
            shipment_id=shipment_id,
            worker_id=worker_id,
        )
        await self.repository.mark_unknown(
            session,
            shipment,
            attempt,
            error_code=error_code,
            provider_uuid=provider_uuid,
            now=now,
        )
        await session.commit()
        return self._result(shipment)

    async def _fail(
        self,
        session: AsyncSession,
        *,
        shipment_id: int,
        worker_id: str,
        now: datetime,
        error_code: str,
        permanent: bool,
        provider_uuid: str | None = None,
    ) -> CdekProcessingResult:
        shipment, attempt = await self._owned(
            session,
            shipment_id=shipment_id,
            worker_id=worker_id,
        )
        retry_delay = min(
            self.policy.retry_base * (2 ** max(0, shipment.attempts_count - 1)),
            self.policy.retry_cap,
        )
        await self.repository.mark_failed(
            session,
            shipment,
            attempt,
            available_at=now + retry_delay,
            error_code=error_code,
            permanent=permanent,
            provider_uuid=provider_uuid,
            now=now,
        )
        await session.commit()
        return self._result(shipment)

    async def _owned(
        self,
        session: AsyncSession,
        *,
        shipment_id: int,
        worker_id: str,
    ) -> tuple[CdekShipment, CdekShipmentAttempt]:
        owned = await self.repository.get_owned_processing_for_update(
            session,
            shipment_id=shipment_id,
            worker_id=worker_id,
        )
        if owned is None:
            raise CdekShipmentOwnershipError("CDEK shipment is no longer owned by this worker")
        return owned

    @staticmethod
    def _result(shipment: CdekShipment) -> CdekProcessingResult:
        return CdekProcessingResult(
            shipment_id=shipment.id,
            status=shipment.status,
            attempt_number=shipment.attempts_count,
            provider_uuid=shipment.provider_uuid,
            error_code=shipment.last_error_code,
        )


TERMINAL_CDEK_SHIPMENT_STATUSES = frozenset(
    {
        CdekShipmentStatus.UNKNOWN.value,
        CdekShipmentStatus.CREATED.value,
        CdekShipmentStatus.DEAD.value,
    }
)
