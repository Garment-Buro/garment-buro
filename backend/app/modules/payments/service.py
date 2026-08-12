from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppEnvironment, Settings, get_settings
from app.modules.identity.security import ensure_utc
from app.modules.orders.models import Order, OrderPaymentStatus, OrderStatus
from app.modules.payments.models import (
    Payment,
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentEvent,
    PaymentProvider,
    PaymentStatus,
)
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import (
    ProviderPaymentEventObservation,
    ProviderPaymentSnapshot,
    YooKassaWebhookEnvelope,
)
from app.modules.payments.security import (
    digest_payment_attempt_key,
    is_trusted_yookassa_webhook_ip,
)

MAX_PAYMENT_WEBHOOK_BYTES = 256 * 1024
SAFE_ERROR_CODE_PATTERN = re.compile(r"^[a-z0-9_.-]{1,64}$")
PAYMENT_METHOD_MAP = {"card": "bank_card", "qr": "sbp"}


class PaymentStateError(ValueError):
    pass


class PaymentIdempotencyConflictError(ValueError):
    pass


class PaymentAttemptInProgressError(ValueError):
    pass


class PaymentProviderMismatchError(ValueError):
    pass


class PaymentEventConflictError(ValueError):
    pass


class UntrustedPaymentWebhookError(ValueError):
    pass


class InvalidPaymentWebhookError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedPaymentAttempt:
    payment_id: int
    attempt_id: int
    order_id: int
    attempt_number: int
    provider_idempotence_key: str
    payment_method: str
    amount: Decimal
    currency: str
    status: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class PaymentEventIntakeResult:
    event_id: int
    status: str
    duplicate: bool
    linked_attempt_id: int | None


class PaymentService:
    def __init__(
        self,
        settings: Settings | None = None,
        repository: PaymentRepository | None = None,
        provider_key_factory: Callable[[], str] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or PaymentRepository()
        self.provider_key_factory = provider_key_factory or (lambda: str(uuid.uuid4()))

    async def prepare_attempt(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        client_attempt_key: str,
    ) -> PreparedPaymentAttempt:
        client_key_digest = digest_payment_attempt_key(client_attempt_key)
        existing = await self.repository.get_attempt_by_client_digest(
            session,
            client_key_digest_sha256=client_key_digest,
            for_update=True,
        )
        order = await self.repository.get_order_for_update(session, order_id=order_id)
        if order is None:
            raise PaymentStateError("Order does not exist")
        if await self.repository.is_legacy_import(session, order_id=order.id):
            raise PaymentStateError("Imported order is not owned by the target payment domain")
        payment_method = PAYMENT_METHOD_MAP.get(order.payment_method or "")
        if payment_method is None:
            raise PaymentStateError("Order payment method is not supported by YooKassa")
        fingerprint = self._attempt_fingerprint(order, payment_method=payment_method)

        if existing is not None:
            return self._replay(existing, order=order, fingerprint=fingerprint)

        existing = await self.repository.get_attempt_by_client_digest(
            session,
            client_key_digest_sha256=client_key_digest,
            for_update=True,
        )
        if existing is not None:
            return self._replay(existing, order=order, fingerprint=fingerprint)

        self._validate_payable_order(order)

        payment = await self.repository.get_payment_for_update(session, order_id=order.id)
        if payment is None:
            payment = Payment(
                order_id=order.id,
                provider=PaymentProvider.YOOKASSA.value,
                status=PaymentStatus.PENDING.value,
                amount=order.total_price,
                currency=order.currency,
            )
            await self.repository.add_payment(session, payment)
        else:
            self._validate_payment_snapshot(payment, order)
            if payment.status == PaymentStatus.SUCCEEDED.value:
                raise PaymentStateError("Order payment has already succeeded")

        active_attempt = await self.repository.get_open_attempt(session, payment_id=payment.id)
        if active_attempt is not None:
            raise PaymentAttemptInProgressError("Another payment attempt is still active")

        payment.status = PaymentStatus.PENDING.value
        attempt = PaymentAttempt(
            payment_id=payment.id,
            attempt_number=await self.repository.next_attempt_number(
                session,
                payment_id=payment.id,
            ),
            client_key_digest_sha256=client_key_digest,
            provider_idempotence_key=self._provider_key(),
            request_fingerprint_sha256=fingerprint,
            payment_method=payment_method,
            status=PaymentAttemptStatus.PREPARED.value,
        )
        stored, inserted = await self.repository.add_attempt(session, attempt)
        if not inserted:
            return self._replay(stored, order=order, fingerprint=fingerprint)
        return self._prepared(stored, payment=payment, replayed=False)

    async def mark_creation_unknown(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        error_code: str,
        now: datetime | None = None,
    ) -> PreparedPaymentAttempt:
        if not SAFE_ERROR_CODE_PATTERN.fullmatch(error_code):
            raise ValueError("Payment error code is not safe to persist")
        attempt = await self._attempt_for_update(session, attempt_id)
        if attempt.status not in {
            PaymentAttemptStatus.PREPARED.value,
            PaymentAttemptStatus.UNKNOWN.value,
        }:
            raise PaymentStateError("Provider creation outcome is already known")
        attempt.status = PaymentAttemptStatus.UNKNOWN.value
        attempt.last_error_code = error_code
        if attempt.provider_payment_id is not None:
            await self._ensure_reconciliation_job(
                session,
                attempt_id=attempt.id,
                now=ensure_utc(now or datetime.now(timezone.utc)),
            )
        await session.flush()
        return self._prepared(attempt, payment=attempt.payment, replayed=False)

    async def mark_creation_failed(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        error_code: str,
        now: datetime | None = None,
    ) -> PreparedPaymentAttempt:
        if not SAFE_ERROR_CODE_PATTERN.fullmatch(error_code):
            raise ValueError("Payment error code is not safe to persist")
        attempt = await self._attempt_for_update(session, attempt_id)
        if attempt.status not in {
            PaymentAttemptStatus.PREPARED.value,
            PaymentAttemptStatus.UNKNOWN.value,
        }:
            raise PaymentStateError("Provider creation outcome is already known")
        attempt.status = PaymentAttemptStatus.FAILED.value
        attempt.resolved_at = max(
            ensure_utc(now or datetime.now(timezone.utc)),
            ensure_utc(attempt.created_at),
        )
        attempt.last_error_code = error_code
        await session.flush()
        return self._prepared(attempt, payment=attempt.payment, replayed=False)

    async def remember_unknown_provider_identity(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        snapshot: ProviderPaymentSnapshot,
        error_code: str,
        now: datetime | None = None,
    ) -> PreparedPaymentAttempt:
        if not SAFE_ERROR_CODE_PATTERN.fullmatch(error_code):
            raise ValueError("Payment error code is not safe to persist")
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        attempt = await self._attempt_for_update(session, attempt_id)
        if attempt.status not in {
            PaymentAttemptStatus.PREPARED.value,
            PaymentAttemptStatus.UNKNOWN.value,
        }:
            raise PaymentStateError("Provider creation outcome is already known")
        self._validate_provider_snapshot(attempt.payment, attempt, snapshot)
        attempt.provider_payment_id = snapshot.provider_payment_id
        attempt.provider_created_at = attempt.provider_created_at or self._optional_utc(
            snapshot.provider_created_at
        )
        attempt.confirmation_url = snapshot.confirmation_url
        attempt.status = PaymentAttemptStatus.UNKNOWN.value
        attempt.last_error_code = error_code
        await self._ensure_reconciliation_job(
            session,
            attempt_id=attempt.id,
            now=current_time,
        )
        await session.flush()
        return self._prepared(attempt, payment=attempt.payment, replayed=False)

    async def record_provider_snapshot(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        snapshot: ProviderPaymentSnapshot,
        now: datetime | None = None,
        manage_reconciliation: bool = True,
    ) -> PreparedPaymentAttempt:
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        attempt = await self._attempt_for_update(session, attempt_id)
        payment = attempt.payment
        self._validate_provider_snapshot(payment, attempt, snapshot)
        self._validate_provider_transition(attempt.status, snapshot.status)
        self._validate_terminal_replay(attempt, snapshot)

        attempt.provider_payment_id = snapshot.provider_payment_id
        attempt.status = snapshot.status
        attempt.confirmation_url = snapshot.confirmation_url
        attempt.provider_created_at = attempt.provider_created_at or self._optional_utc(
            snapshot.provider_created_at
        )
        attempt.captured_at = attempt.captured_at or self._optional_utc(snapshot.captured_at)
        attempt.cancellation_party = snapshot.cancellation_party
        attempt.cancellation_reason = snapshot.cancellation_reason
        attempt.last_error_code = None
        if snapshot.status in {
            PaymentAttemptStatus.SUCCEEDED.value,
            PaymentAttemptStatus.CANCELED.value,
        }:
            attempt.resolved_at = attempt.resolved_at or max(
                current_time,
                ensure_utc(attempt.created_at),
            )

        if snapshot.status == PaymentAttemptStatus.SUCCEEDED.value:
            payment.status = PaymentStatus.SUCCEEDED.value
            payment.succeeded_at = payment.succeeded_at or current_time
        elif snapshot.status == PaymentAttemptStatus.CANCELED.value:
            if payment.status != PaymentStatus.SUCCEEDED.value:
                payment.status = PaymentStatus.CANCELED.value
        else:
            payment.status = PaymentStatus.PENDING.value
        if manage_reconciliation:
            await self._sync_reconciliation_job(
                session,
                attempt=attempt,
                now=current_time,
            )
        await session.flush()
        return self._prepared(attempt, payment=payment, replayed=False)

    async def intake_event(
        self,
        session: AsyncSession,
        *,
        raw_body: bytes,
        source_ip: str,
        now: datetime | None = None,
        max_attempts: int | None = None,
    ) -> PaymentEventIntakeResult:
        if not is_trusted_yookassa_webhook_ip(source_ip):
            raise UntrustedPaymentWebhookError("Webhook source is not trusted")
        if not 1 <= len(raw_body) <= MAX_PAYMENT_WEBHOOK_BYTES:
            raise ValueError("Payment webhook body size is invalid")
        effective_max_attempts = (
            self.settings.payment_event_max_attempts if max_attempts is None else max_attempts
        )
        if not 1 <= effective_max_attempts <= 20:
            raise ValueError("Payment event max attempts must be between 1 and 20")
        observation = self._parse_webhook(raw_body)
        current_time = ensure_utc(now or datetime.now(timezone.utc))
        snapshot = observation.payment
        event_key = self._digest(
            f"{PaymentProvider.YOOKASSA.value}:{observation.event_type}:"
            f"{snapshot.provider_payment_id}"
        )
        observation_digest = self._observation_digest(observation)
        attempt = await self.repository.find_attempt_by_provider_id(
            session,
            provider_payment_id=snapshot.provider_payment_id,
        )
        event = PaymentEvent(
            payment_attempt_id=attempt.id if attempt is not None else None,
            event_key_sha256=event_key,
            payload_sha256=hashlib.sha256(raw_body).hexdigest(),
            observation_sha256=observation_digest,
            event_type=observation.event_type,
            provider_payment_id=snapshot.provider_payment_id,
            observed_status=snapshot.status,
            observed_amount=snapshot.amount,
            observed_currency=snapshot.currency,
            observed_paid=snapshot.paid,
            observed_test=snapshot.test,
            metadata_order_id=snapshot.metadata_order_id,
            source_ip=self._normalized_source_ip(source_ip),
            provider_created_at=self._optional_utc(snapshot.provider_created_at),
            captured_at=self._optional_utc(snapshot.captured_at),
            cancellation_party=snapshot.cancellation_party,
            cancellation_reason=snapshot.cancellation_reason,
            max_attempts=effective_max_attempts,
            available_at=current_time,
        )
        stored, inserted = await self.repository.add_event(session, event)
        if not inserted and stored.observation_sha256 != observation_digest:
            raise PaymentEventConflictError("Duplicate payment event has changed evidence")
        return PaymentEventIntakeResult(
            event_id=stored.id,
            status=stored.status,
            duplicate=not inserted,
            linked_attempt_id=stored.payment_attempt_id,
        )

    @staticmethod
    def _validate_payable_order(order: Order) -> None:
        if (
            order.status != OrderStatus.NEW.value
            or order.payment_status != OrderPaymentStatus.PENDING.value
        ):
            raise PaymentStateError("Order is not awaiting payment")
        if order.total_price <= 0:
            raise PaymentStateError("Order total must be positive")
        if order.currency != "RUB":
            raise PaymentStateError("Order currency is not supported")
        if not order.email_normalized:
            raise PaymentStateError("Order receipt email is required")

    @staticmethod
    def _validate_payment_snapshot(payment: Payment, order: Order) -> None:
        if (
            payment.provider != PaymentProvider.YOOKASSA.value
            or payment.amount != order.total_price
            or payment.currency != order.currency
        ):
            raise PaymentProviderMismatchError("Persisted payment does not match the order")

    def _validate_provider_snapshot(
        self,
        payment: Payment,
        attempt: PaymentAttempt,
        snapshot: ProviderPaymentSnapshot,
    ) -> None:
        if (
            snapshot.metadata_order_id != payment.order_id
            or snapshot.amount != payment.amount
            or snapshot.currency != payment.currency
            or (
                snapshot.payment_method is None
                and snapshot.status != PaymentAttemptStatus.CANCELED.value
            )
            or (
                snapshot.payment_method is not None
                and snapshot.payment_method != attempt.payment_method
            )
        ):
            raise PaymentProviderMismatchError("Provider payment does not match the attempt")
        if (
            attempt.provider_payment_id is not None
            and attempt.provider_payment_id != snapshot.provider_payment_id
        ):
            raise PaymentProviderMismatchError("Attempt is already linked to another payment")
        if self.settings.app_env == AppEnvironment.PRODUCTION and snapshot.test:
            raise PaymentProviderMismatchError("Production refused a YooKassa test payment")
        if self.settings.app_env == AppEnvironment.STAGING and not snapshot.test:
            raise PaymentProviderMismatchError("Staging refused a live YooKassa payment")

    @staticmethod
    def _validate_provider_transition(current: str, observed: str) -> None:
        allowed = {
            PaymentAttemptStatus.PREPARED.value: {
                PaymentAttemptStatus.PENDING.value,
                PaymentAttemptStatus.WAITING_FOR_CAPTURE.value,
                PaymentAttemptStatus.SUCCEEDED.value,
                PaymentAttemptStatus.CANCELED.value,
            },
            PaymentAttemptStatus.UNKNOWN.value: {
                PaymentAttemptStatus.PENDING.value,
                PaymentAttemptStatus.WAITING_FOR_CAPTURE.value,
                PaymentAttemptStatus.SUCCEEDED.value,
                PaymentAttemptStatus.CANCELED.value,
            },
            PaymentAttemptStatus.PENDING.value: {
                PaymentAttemptStatus.PENDING.value,
                PaymentAttemptStatus.WAITING_FOR_CAPTURE.value,
                PaymentAttemptStatus.SUCCEEDED.value,
                PaymentAttemptStatus.CANCELED.value,
            },
            PaymentAttemptStatus.WAITING_FOR_CAPTURE.value: {
                PaymentAttemptStatus.WAITING_FOR_CAPTURE.value,
                PaymentAttemptStatus.SUCCEEDED.value,
                PaymentAttemptStatus.CANCELED.value,
            },
            PaymentAttemptStatus.SUCCEEDED.value: {PaymentAttemptStatus.SUCCEEDED.value},
            PaymentAttemptStatus.CANCELED.value: {PaymentAttemptStatus.CANCELED.value},
            PaymentAttemptStatus.FAILED.value: set(),
        }
        if observed not in allowed.get(current, set()):
            raise PaymentStateError(f"Payment cannot transition from {current} to {observed}")

    @staticmethod
    def _validate_terminal_replay(
        attempt: PaymentAttempt,
        snapshot: ProviderPaymentSnapshot,
    ) -> None:
        if attempt.status not in {
            PaymentAttemptStatus.SUCCEEDED.value,
            PaymentAttemptStatus.CANCELED.value,
        }:
            return
        evidence = {
            "provider_created_at": PaymentService._optional_utc(snapshot.provider_created_at),
            "captured_at": PaymentService._optional_utc(snapshot.captured_at),
            "cancellation_party": snapshot.cancellation_party,
            "cancellation_reason": snapshot.cancellation_reason,
        }
        for field_name, observed in evidence.items():
            persisted = getattr(attempt, field_name)
            if isinstance(persisted, datetime):
                persisted = ensure_utc(persisted)
            if persisted is not None and observed is not None and persisted != observed:
                raise PaymentProviderMismatchError(
                    f"Terminal payment evidence changed: {field_name}"
                )

    @staticmethod
    def _attempt_fingerprint(order: Order, *, payment_method: str) -> str:
        canonical = {
            "order_id": order.id,
            "amount": format(order.total_price, ".2f"),
            "currency": order.currency,
            "payment_method": payment_method,
        }
        return hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _provider_key(self) -> str:
        value = self.provider_key_factory()
        try:
            parsed = uuid.UUID(value)
        except (AttributeError, TypeError, ValueError) as error:
            raise RuntimeError(
                "Provider idempotence key factory returned an invalid UUID"
            ) from error
        if parsed.version != 4 or str(parsed) != value:
            raise RuntimeError("Provider idempotence key must be a canonical UUIDv4")
        return value

    @staticmethod
    def _replay(
        attempt: PaymentAttempt,
        *,
        order: Order,
        fingerprint: str,
    ) -> PreparedPaymentAttempt:
        if (
            attempt.payment.order_id != order.id
            or attempt.request_fingerprint_sha256 != fingerprint
        ):
            raise PaymentIdempotencyConflictError(
                "Payment attempt key was already used for another request"
            )
        return PaymentService._prepared(attempt, payment=attempt.payment, replayed=True)

    async def _attempt_for_update(
        self,
        session: AsyncSession,
        attempt_id: int,
    ) -> PaymentAttempt:
        attempt = await self.repository.get_attempt_for_update(session, attempt_id=attempt_id)
        if attempt is None:
            raise PaymentStateError("Payment attempt does not exist")
        return attempt

    @staticmethod
    def _prepared(
        attempt: PaymentAttempt,
        *,
        payment: Payment,
        replayed: bool,
    ) -> PreparedPaymentAttempt:
        return PreparedPaymentAttempt(
            payment_id=payment.id,
            attempt_id=attempt.id,
            order_id=payment.order_id,
            attempt_number=attempt.attempt_number,
            provider_idempotence_key=attempt.provider_idempotence_key,
            payment_method=attempt.payment_method,
            amount=payment.amount,
            currency=payment.currency,
            status=attempt.status,
            replayed=replayed,
        )

    @staticmethod
    def _observation_digest(observation: ProviderPaymentEventObservation) -> str:
        return hashlib.sha256(
            json.dumps(
                observation.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def provider_snapshot_digest(snapshot: ProviderPaymentSnapshot) -> str:
        return hashlib.sha256(
            json.dumps(
                snapshot.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    async def _sync_reconciliation_job(
        self,
        session: AsyncSession,
        *,
        attempt: PaymentAttempt,
        now: datetime,
    ) -> None:
        if attempt.status in {
            PaymentAttemptStatus.SUCCEEDED.value,
            PaymentAttemptStatus.CANCELED.value,
        }:
            job = await self.repository.get_reconciliation_job_for_attempt_for_update(
                session,
                attempt_id=attempt.id,
            )
            if job is not None:
                await self.repository.mark_reconciliation_completed(
                    session,
                    job,
                    completed_at=now,
                )
            return
        if attempt.provider_payment_id is not None and attempt.status in {
            PaymentAttemptStatus.UNKNOWN.value,
            PaymentAttemptStatus.PENDING.value,
            PaymentAttemptStatus.WAITING_FOR_CAPTURE.value,
        }:
            await self._ensure_reconciliation_job(
                session,
                attempt_id=attempt.id,
                now=now,
            )

    async def _ensure_reconciliation_job(
        self,
        session: AsyncSession,
        *,
        attempt_id: int,
        now: datetime,
    ) -> None:
        await self.repository.ensure_reconciliation_job(
            session,
            attempt_id=attempt_id,
            available_at=ensure_utc(now)
            + timedelta(seconds=self.settings.payment_reconciliation_interval_seconds),
            max_attempts=self.settings.payment_reconciliation_max_attempts,
        )

    @staticmethod
    def _parse_webhook(raw_body: bytes) -> ProviderPaymentEventObservation:
        try:
            envelope = YooKassaWebhookEnvelope.model_validate_json(raw_body)
            return envelope.to_observation()
        except (TypeError, ValueError) as error:
            raise InvalidPaymentWebhookError("Invalid YooKassa webhook payload") from error

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalized_source_ip(value: str) -> str:
        address = ipaddress.ip_address(value.strip())
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        return str(address)

    @staticmethod
    def _optional_utc(value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None
