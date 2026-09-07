from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.tochka.mapping import bank_request
from app.modules.bank_payouts.contracts import BankPayoutProvider, BankProviderError
from app.modules.bank_payouts.models import PartnerBankPayment
from app.modules.bank_payouts.repository import BankPayoutRepository
from app.modules.bank_payouts.schemas import BankPayoutCreate
from app.modules.identity.security import ensure_utc
from app.modules.partners.schemas import PartnerRequisitesRequest
from app.modules.partners.service import PartnerProgramService

TERMINAL = {"paid", "rejected", "canceled"}
STATUS_MAP = {
    "WaitingForCreate": "awaiting_signature",
    "Created": "processing",
    "Paid": "paid",
    "Rejected": "rejected",
    "Canceled": "canceled",
}


class BankPayoutConflict(ValueError):
    pass


class BankPayoutNotFound(LookupError):
    pass


class BankPayoutDisabled(RuntimeError):
    pass


class PartnerBankPayoutService:
    def __init__(
        self,
        settings: Settings,
        provider: BankPayoutProvider,
        partners: PartnerProgramService,
        repository: BankPayoutRepository | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.partners = partners
        self.repository = repository or BankPayoutRepository()

    def require_enabled(self) -> None:
        if not self.settings.tochka_payouts_enabled:
            raise BankPayoutDisabled("Tochka payouts are disabled")

    async def create(
        self,
        session: AsyncSession,
        *,
        payout_id: int,
        command: BankPayoutCreate,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> PartnerBankPayment:
        self.require_enabled()
        observed_at = ensure_utc(now or datetime.now(timezone.utc))
        # Serialize against admin review and other submissions. Unique payout_id is the
        # cross-process backstop (including DBs without SELECT FOR UPDATE).
        payout = await self.partners.repository.get_payout_for_update(session, payout_id=payout_id)
        if payout is None:
            raise BankPayoutNotFound("Payout request was not found")
        codec = self.partners.requisites_codec
        if codec is None:
            raise BankPayoutDisabled("Requisites encryption is unavailable")
        digest = codec.digest(
            {
                "payout_id": payout_id,
                "environment": self.settings.tochka_environment,
                "purpose": command.payment_purpose,
            }
        )
        existing = await self.repository.get(session, payout_id, lock=True)
        if existing:
            if existing.command_sha256 != digest:
                raise BankPayoutConflict(
                    "A bank operation already exists with different parameters"
                )
            return existing
        if payout.status != "approved":
            raise BankPayoutConflict("Approve the withdrawal before creating a bank payment")
        profile = await self.partners.repository.get_profile(session, partner_id=payout.partner_id)
        if profile is None or profile.status != "active":
            raise BankPayoutConflict("Partner is not active")
        if not await self.repository.funds_cover_reservations(
            session, payout.partner_id, observed_at
        ):
            raise BankPayoutConflict("Commission balance no longer covers reserved withdrawals")
        requisites = await self.partners.get_requisites(session, user_id=profile.user_id)
        if requisites is None:
            raise BankPayoutConflict("Partner requisites are missing")
        try:
            payload, body = bank_request(
                settings=self.settings,
                payout_id=payout.id,
                amount=payout.amount,
                requisites=PartnerRequisitesRequest.model_validate(
                    requisites.model_dump(exclude={"updated_at"})
                ),
                purpose=command.payment_purpose,
                now=observed_at,
            )
        except ValueError as error:
            raise BankPayoutConflict(str(error)) from error
        encrypted = codec.encrypt(
            {"payout_id": payout.id, "request": payload}, partner_id=payout.partner_id
        )
        payment = PartnerBankPayment(
            payout_id=payout.id,
            environment=self.settings.tochka_environment,
            state="submitting",
            command_sha256=digest,
            created_by_user_id=actor_user_id,
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
            tag=encrypted.tag,
            key_version=encrypted.key_version,
            schema_version=encrypted.schema_version,
            last_checked_at=observed_at,
        )
        session.add(payment)
        try:
            await session.flush()
            await self.repository.event(session, payment, observed_at)
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            existing = await self.repository.get(session, payout_id)
            if existing is not None and existing.command_sha256 == digest:
                return existing
            raise BankPayoutConflict("Concurrent bank operation already exists") from error

        # The reservation is durable before any bank side effect. Never resend, even
        # after a process crash, timeout, HTTP 5xx, or an invalid success response.
        try:
            draft = await self.provider.create_draft(body)
        except BankProviderError as error:
            payout = await self.partners.repository.get_payout_for_update(
                session, payout_id=payout_id
            )
            payment = await self.repository.get(session, payout_id, lock=True)
            if payment is None or payout is None:
                raise BankPayoutNotFound("Bank operation was not found") from error
            payment.state = "unknown" if error.outcome_unknown else "rejected"
            payment.last_error = error.code
            if not error.outcome_unknown:
                payout.status = "rejected"
            await self.repository.event(session, payment, observed_at)
            await session.commit()
            return payment
        await self.partners.repository.get_payout_for_update(session, payout_id=payout_id)
        payment = await self.repository.get(session, payout_id, lock=True)
        if payment is None:
            raise BankPayoutNotFound("Bank operation was not found")
        payment.request_id = draft.request_id
        payment.signing_url = draft.signing_url
        payment.state = "awaiting_signature"
        payment.provider_status = "WaitingForCreate"
        payment.last_error = None
        await self.repository.event(session, payment, observed_at)
        await session.commit()
        return payment

    async def reconcile(
        self,
        session: AsyncSession,
        *,
        payout_id: int,
        now: datetime | None = None,
    ) -> PartnerBankPayment:
        self.require_enabled()
        observed_at = ensure_utc(now or datetime.now(timezone.utc))
        # All paths lock payout then bank operation to avoid review/poll deadlocks.
        payout = await self.partners.repository.get_payout_for_update(session, payout_id=payout_id)
        payment = await self.repository.get(session, payout_id, lock=True)
        if payout is None or payment is None:
            raise BankPayoutNotFound("Bank operation was not found")
        if payment.environment != self.settings.tochka_environment:
            raise BankPayoutConflict("Cannot reconcile a payment from another bank environment")
        if payment.state in TERMINAL:
            return payment
        if payment.request_id is None:
            if payment.state != "unknown" and observed_at - ensure_utc(
                payment.created_at
            ) > timedelta(seconds=120):
                payment.state = "unknown"
                payment.last_error = "bank_receipt_missing"
                await self.repository.event(session, payment, observed_at)
            payment.last_checked_at = observed_at
            await session.commit()
            return payment
        try:
            snapshot = await self.provider.get_status(payment.request_id)
            if snapshot.request_id != payment.request_id or snapshot.status not in STATUS_MAP:
                raise BankProviderError("invalid_status_evidence")
        except BankProviderError as error:
            payment.last_error = error.code
            payment.last_checked_at = observed_at
            await session.commit()
            return payment
        state = STATUS_MAP[snapshot.status]
        # Ignore older nonterminal observations. Terminal states are never reversed.
        if payment.state == "processing" and state == "awaiting_signature":
            state = "processing"
        changed = payment.state != state
        payment.state = state
        if not (state == "processing" and snapshot.status == "WaitingForCreate"):
            payment.provider_status = snapshot.status
        payment.last_error = None
        payment.last_checked_at = observed_at
        if state in TERMINAL:
            payout.status = state
            if state == "paid":
                payout.paid_at = observed_at
        if changed:
            await self.repository.event(session, payment, observed_at)
        await session.commit()
        return payment
