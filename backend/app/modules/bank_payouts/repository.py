from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bank_payouts.models import PartnerBankPayment, PartnerBankPaymentEvent
from app.modules.partners.models import PartnerCommission, PartnerPayoutRequest


class BankPayoutRepository:
    async def get(
        self, session: AsyncSession, payout_id: int, *, lock: bool = False
    ) -> PartnerBankPayment | None:
        statement = select(PartnerBankPayment).where(PartnerBankPayment.payout_id == payout_id)
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement.execution_options(populate_existing=True))

    async def pending_ids(
        self, session: AsyncSession, *, before: datetime, limit: int = 50
    ) -> list[int]:
        return list(
            await session.scalars(
                select(PartnerBankPayment.payout_id)
                .where(
                    PartnerBankPayment.state.in_(
                        ("submitting", "unknown", "awaiting_signature", "processing")
                    ),
                    (PartnerBankPayment.last_checked_at.is_(None))
                    | (PartnerBankPayment.last_checked_at < before),
                )
                .order_by(
                    PartnerBankPayment.last_checked_at.asc().nullsfirst(), PartnerBankPayment.id
                )
                .limit(limit)
            )
        )

    async def funds_cover_reservations(
        self, session: AsyncSession, partner_id: int, now: datetime
    ) -> bool:
        matured = await session.scalar(
            select(func.coalesce(func.sum(PartnerCommission.amount), 0)).where(
                PartnerCommission.partner_id == partner_id,
                PartnerCommission.status == "pending",
                PartnerCommission.available_at <= now,
            )
        )
        reserved = await session.scalar(
            select(func.coalesce(func.sum(PartnerPayoutRequest.amount), 0)).where(
                PartnerPayoutRequest.partner_id == partner_id,
                PartnerPayoutRequest.status.in_(("requested", "approved", "paid")),
            )
        )
        return Decimal(matured or 0) >= Decimal(reserved or 0)

    async def event(
        self, session: AsyncSession, payment: PartnerBankPayment, now: datetime
    ) -> None:
        session.add(
            PartnerBankPaymentEvent(
                payment_id=payment.id,
                state=payment.state,
                provider_status=payment.provider_status,
                error_code=payment.last_error,
                observed_at=now,
            )
        )
        await session.flush()
