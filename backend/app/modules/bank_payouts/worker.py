import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.db.session import DatabaseManager
from app.modules.bank_payouts.service import BankPayoutConflict, PartnerBankPayoutService

logger = logging.getLogger(__name__)


async def reconcile_bank_payouts(
    database: DatabaseManager, service: PartnerBankPayoutService
) -> None:
    """Read-only bank polling; this worker can never create or sign a payment."""
    while True:
        try:
            async with database.session() as session:
                ids = await service.repository.pending_ids(
                    session,
                    before=datetime.now(timezone.utc)
                    - timedelta(seconds=service.settings.tochka_poll_seconds),
                )
            for payout_id in ids:
                try:
                    async with database.session() as session:
                        await service.reconcile(session, payout_id=payout_id)
                except (SQLAlchemyError, BankPayoutConflict):
                    logger.warning(
                        "Bank payout reconciliation requires review: payout_id=%s", payout_id
                    )
        except SQLAlchemyError:
            logger.warning("Bank payout reconciliation database is unavailable")
        await asyncio.sleep(service.settings.tochka_poll_seconds)
