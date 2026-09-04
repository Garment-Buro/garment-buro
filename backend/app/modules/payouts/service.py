from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppEnvironment, Settings
from app.modules.identity.security import ensure_utc
from app.modules.payments.security import digest_payment_attempt_key
from app.modules.payouts.models import Payout, PayoutStatus
from app.modules.payouts.provider import (
    YooKassaPayoutProvider,
    YooKassaPayoutProviderError,
)
from app.modules.payouts.repository import PayoutRepository
from app.modules.payouts.schemas import PayoutCreateCommand, PayoutResponse, YooKassaPayoutResponse


class PayoutDisabledError(RuntimeError):
    pass


class PayoutNotFoundError(LookupError):
    pass


class PayoutConflictError(ValueError):
    pass


class PayoutInProgressError(RuntimeError):
    pass


class PayoutProviderFailedError(RuntimeError):
    def __init__(self, code: str, *, outcome_unknown: bool) -> None:
        super().__init__(f"Payout provider request failed: {code}")
        self.code = code
        self.outcome_unknown = outcome_unknown


class PayoutService:
    """Create and reconcile payouts without persisting raw destination credentials."""

    def __init__(
        self,
        settings: Settings,
        provider: YooKassaPayoutProvider,
        *,
        repository: PayoutRepository | None = None,
        provider_key_factory: Callable[[], str] | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.repository = repository or PayoutRepository()
        self.provider_key_factory = provider_key_factory or (lambda: str(uuid.uuid4()))

    async def create(
        self,
        session: AsyncSession,
        *,
        command: PayoutCreateCommand,
        client_key: str,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> PayoutResponse:
        self._require_enabled()
        if actor_user_id <= 0:
            raise PayoutConflictError("Payout actor is invalid")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        client_digest = digest_payment_attempt_key(client_key)
        payout = await self.repository.get_by_client_digest(
            session,
            client_key_digest_sha256=client_digest,
            for_update=True,
        )
        inserted = False
        if payout is None:
            payout = Payout(
                actor_user_id=actor_user_id,
                client_key_digest_sha256=client_digest,
                provider_idempotence_key=self._provider_key(),
                amount=command.amount.value,
                currency=command.amount.currency,
                description=command.description,
                reference=command.reference,
                requested_destination_type=command.destination.type,
                status=PayoutStatus.PREPARED.value,
                attempts_count=0,
            )
            payout, inserted = await self.repository.add(session, payout)

        request_body = command.canonical_provider_bytes(internal_payout_id=payout.id)
        request_digest = hashlib.sha256(request_body).hexdigest()
        self._validate_replay(
            payout,
            client_digest=client_digest,
            request_digest=request_digest,
            actor_user_id=actor_user_id,
        )
        if payout.status in {
            PayoutStatus.PENDING.value,
            PayoutStatus.SUCCEEDED.value,
            PayoutStatus.CANCELED.value,
        }:
            return self._response(payout, replayed=True)
        if payout.status == PayoutStatus.FAILED.value:
            raise PayoutProviderFailedError(
                payout.last_error_code or "payout_failed",
                outcome_unknown=False,
            )
        if not inserted:
            if current_time - ensure_utc(payout.created_at) > timedelta(
                seconds=self.settings.payout_retry_window_seconds
            ):
                payout.status = PayoutStatus.FAILED.value
                payout.resolved_at = max(current_time, ensure_utc(payout.created_at))
                payout.last_error_code = "idempotence_window_expired"
                await session.commit()
                raise PayoutConflictError("Payout idempotence replay window expired")
            if payout.last_attempt_at is not None and current_time - ensure_utc(
                payout.last_attempt_at
            ) < timedelta(seconds=self.settings.payout_processing_timeout_seconds):
                raise PayoutInProgressError("Payout creation is already in progress")

        payout.request_sha256 = request_digest
        payout.status = PayoutStatus.PREPARED.value
        payout.attempts_count += 1
        payout.last_attempt_at = current_time
        payout.last_error_code = None
        await session.commit()

        try:
            snapshot = await self.provider.create_payout(
                idempotence_key=payout.provider_idempotence_key,
                request_body=request_body,
            )
        except YooKassaPayoutProviderError as error:
            await self._persist_provider_failure(
                session,
                payout_id=payout.id,
                code=error.code,
                outcome_unknown=error.outcome_unknown,
                now=current_time,
            )
            raise PayoutProviderFailedError(
                error.code,
                outcome_unknown=error.outcome_unknown,
            ) from error
        except Exception as error:  # noqa: BLE001 - an external transfer may have started
            await self._persist_provider_failure(
                session,
                payout_id=payout.id,
                code="provider_unexpected",
                outcome_unknown=True,
                now=current_time,
            )
            raise PayoutProviderFailedError(
                "provider_unexpected",
                outcome_unknown=True,
            ) from error

        try:
            stored = await self._apply_snapshot(
                session,
                payout_id=payout.id,
                snapshot=snapshot,
                now=current_time,
            )
            await session.commit()
            return self._response(stored, replayed=False)
        except Exception as error:  # noqa: BLE001 - preserve uncertain accepted provider evidence
            await session.rollback()
            await self._persist_provider_failure(
                session,
                payout_id=payout.id,
                code="provider_evidence_processing_failed",
                outcome_unknown=True,
                now=current_time,
            )
            raise PayoutProviderFailedError(
                "provider_evidence_processing_failed",
                outcome_unknown=True,
            ) from error

    async def get(self, session: AsyncSession, *, payout_id: int) -> PayoutResponse:
        self._require_enabled()
        payout = await self.repository.get(session, payout_id=payout_id)
        if payout is None:
            raise PayoutNotFoundError("Payout does not exist")
        return self._response(payout, replayed=False)

    async def refresh(
        self,
        session: AsyncSession,
        *,
        payout_id: int,
        now: datetime | None = None,
    ) -> PayoutResponse:
        self._require_enabled()
        payout = await self.repository.get_for_update(session, payout_id=payout_id)
        if payout is None:
            raise PayoutNotFoundError("Payout does not exist")
        if payout.provider_payout_id is None:
            raise PayoutConflictError("Payout has no provider identity yet")
        if payout.status in {
            PayoutStatus.SUCCEEDED.value,
            PayoutStatus.CANCELED.value,
        }:
            return self._response(payout, replayed=True)
        provider_payout_id = payout.provider_payout_id
        try:
            snapshot = await self.provider.get_payout(provider_payout_id)
        except YooKassaPayoutProviderError as error:
            raise PayoutProviderFailedError(error.code, outcome_unknown=False) from error
        stored = await self._apply_snapshot(
            session,
            payout_id=payout.id,
            snapshot=snapshot,
            now=ensure_utc(now or datetime.now(timezone.utc)),
        )
        await session.commit()
        return self._response(stored, replayed=False)

    async def _apply_snapshot(
        self,
        session: AsyncSession,
        *,
        payout_id: int,
        snapshot: YooKassaPayoutResponse,
        now: datetime,
    ) -> Payout:
        payout = await self.repository.get_for_update(session, payout_id=payout_id)
        if payout is None:
            raise PayoutNotFoundError("Payout disappeared after provider call")
        self._validate_snapshot(payout, snapshot)
        allowed = {
            PayoutStatus.PREPARED.value: {
                PayoutStatus.PENDING.value,
                PayoutStatus.SUCCEEDED.value,
                PayoutStatus.CANCELED.value,
            },
            PayoutStatus.UNKNOWN.value: {
                PayoutStatus.PENDING.value,
                PayoutStatus.SUCCEEDED.value,
                PayoutStatus.CANCELED.value,
            },
            PayoutStatus.PENDING.value: {
                PayoutStatus.PENDING.value,
                PayoutStatus.SUCCEEDED.value,
                PayoutStatus.CANCELED.value,
            },
            PayoutStatus.SUCCEEDED.value: {PayoutStatus.SUCCEEDED.value},
            PayoutStatus.CANCELED.value: {PayoutStatus.CANCELED.value},
            PayoutStatus.FAILED.value: set(),
        }
        if snapshot.status not in allowed.get(payout.status, set()):
            raise PayoutConflictError(
                f"Payout cannot transition from {payout.status} to {snapshot.status}"
            )
        evidence_digest = self._snapshot_digest(snapshot)
        if payout.status in {
            PayoutStatus.SUCCEEDED.value,
            PayoutStatus.CANCELED.value,
        } and payout.provider_evidence_sha256 not in {None, evidence_digest}:
            raise PayoutConflictError("Terminal payout evidence changed")

        payout.provider_payout_id = snapshot.id
        payout.provider_destination_type = snapshot.payout_destination.type
        payout.status = snapshot.status
        payout.provider_created_at = payout.provider_created_at or ensure_utc(snapshot.created_at)
        payout.succeeded_at = (
            payout.succeeded_at or ensure_utc(snapshot.succeeded_at)
            if snapshot.succeeded_at is not None
            else None
        )
        cancellation = snapshot.cancellation_details
        payout.cancellation_party = cancellation.party if cancellation is not None else None
        payout.cancellation_reason = cancellation.reason if cancellation is not None else None
        payout.test = snapshot.test
        payout.last_error_code = None
        payout.provider_evidence_sha256 = evidence_digest
        if snapshot.status in {PayoutStatus.SUCCEEDED.value, PayoutStatus.CANCELED.value}:
            payout.resolved_at = payout.resolved_at or max(now, ensure_utc(payout.created_at))
        await session.flush()
        return payout

    async def _persist_provider_failure(
        self,
        session: AsyncSession,
        *,
        payout_id: int,
        code: str,
        outcome_unknown: bool,
        now: datetime,
    ) -> None:
        payout = await self.repository.get_for_update(session, payout_id=payout_id)
        if payout is None:
            raise PayoutNotFoundError("Payout disappeared after provider call")
        if payout.status in {
            PayoutStatus.SUCCEEDED.value,
            PayoutStatus.CANCELED.value,
        }:
            await session.commit()
            return
        payout.status = PayoutStatus.UNKNOWN.value if outcome_unknown else PayoutStatus.FAILED.value
        payout.resolved_at = None if outcome_unknown else max(now, ensure_utc(payout.created_at))
        payout.last_error_code = code
        await session.commit()

    def _validate_snapshot(self, payout: Payout, snapshot: YooKassaPayoutResponse) -> None:
        if (
            snapshot.amount.value != payout.amount
            or snapshot.amount.currency != payout.currency
            or snapshot.description != payout.description
            or snapshot.metadata.internal_payout_id != payout.id
            or snapshot.metadata.reference != payout.reference
            or (payout.provider_payout_id is not None and payout.provider_payout_id != snapshot.id)
        ):
            raise PayoutConflictError("Provider payout does not match the persisted request")
        if self.settings.app_env == AppEnvironment.PRODUCTION and snapshot.test:
            raise PayoutConflictError("Production refused a YooKassa test payout")
        if self.settings.app_env == AppEnvironment.STAGING and not snapshot.test:
            raise PayoutConflictError("Staging refused a live YooKassa payout")

    @staticmethod
    def _validate_replay(
        payout: Payout,
        *,
        client_digest: str,
        request_digest: str,
        actor_user_id: int,
    ) -> None:
        if (
            payout.client_key_digest_sha256 != client_digest
            or payout.actor_user_id != actor_user_id
            or (payout.request_sha256 is not None and payout.request_sha256 != request_digest)
        ):
            raise PayoutConflictError("Payout idempotency key was already used")

    def _require_enabled(self) -> None:
        if not self.settings.yookassa_payouts_enabled:
            raise PayoutDisabledError("YooKassa payouts are disabled")

    def _provider_key(self) -> str:
        value = self.provider_key_factory()
        try:
            parsed = uuid.UUID(value)
        except (AttributeError, TypeError, ValueError) as error:
            raise RuntimeError("Invalid payout provider key") from error
        if parsed.version != 4 or str(parsed) != value:
            raise RuntimeError("Payout provider key must be UUIDv4")
        return value

    @staticmethod
    def _snapshot_digest(snapshot: YooKassaPayoutResponse) -> str:
        return hashlib.sha256(
            json.dumps(
                snapshot.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _response(payout: Payout, *, replayed: bool) -> PayoutResponse:
        return PayoutResponse.model_validate(payout).model_copy(update={"replayed": replayed})
