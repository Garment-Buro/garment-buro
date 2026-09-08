import argparse
import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.delivery.provider import AiohttpCdekTransport, CdekProviderClient
from app.modules.orders.workflow_worker import OrderWorkflowProcessor
from app.modules.payments.provider import AiohttpYooKassaTransport, YooKassaProviderClient

logger = logging.getLogger(__name__)


async def run(once: bool, max_items: int) -> None:
    if not 1 <= max_items <= 1000:
        raise ValueError("max-items must be between 1 and 1000")
    settings = get_settings()
    if not (
        settings.database_enabled
        and settings.payment_creation_enabled
        and settings.payment_management_enabled
    ):
        raise RuntimeError("Database, payment creation and management must be enabled")
    database = DatabaseManager(settings)
    payments = AiohttpYooKassaTransport(settings)
    delivery = AiohttpCdekTransport(settings)
    processor = OrderWorkflowProcessor(
        settings,
        YooKassaProviderClient(payments),
        CdekProviderClient(delivery) if settings.cdek_tracking_enabled else None,
    )
    await database.startup()
    try:
        await payments.startup()
        if settings.cdek_tracking_enabled:
            await delivery.startup()
        while True:
            try:
                async with database.session() as session:
                    await processor.seed_tracking(session, datetime.now(timezone.utc), max_items)
                for _ in range(max_items):
                    async with database.session() as session:
                        if await processor.process_once(session) is None:
                            break
            except Exception:  # noqa: BLE001 - DB outage: persisted leases recover after reconnect
                logger.error("Order worker batch failed; durable jobs retained", exc_info=False)
                if once:
                    raise
            if once:
                return
            await asyncio.sleep(5)
    finally:
        await payments.shutdown()
        await delivery.shutdown()
        await database.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume durable order workflows")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-items", type=int, default=100)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.once, args.max_items))
