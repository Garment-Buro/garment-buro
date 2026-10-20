from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from typing import Protocol

from fastapi import FastAPI

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.bank_payouts.service import PartnerBankPayoutService
from app.modules.bank_payouts.worker import reconcile_bank_payouts
from app.modules.delivery.directory import PickupDirectory

logger = logging.getLogger(__name__)


class RuntimeResource(Protocol):
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...


async def _stop_task(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def _report_task_exit(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    error = task.exception()
    logger.error(
        "Background task exited unexpectedly",
        extra={"event": "runtime.task.failed", "component": task.get_name()},
        exc_info=(type(error), error, error.__traceback__) if error else None,
    )


def build_lifespan(
    *,
    settings: Settings,
    database: DatabaseManager,
    storage: MinioStorage,
    transports: Sequence[RuntimeResource],
    verify_startup: Callable[[], Awaitable[None]],
    bank_payout_service: PartnerBankPayoutService | None,
):
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        tasks: dict[str, asyncio.Task[None]] = {}
        application.state.runtime_tasks = tasks
        logger.info("Application starting", extra={"event": "runtime.starting"})
        try:
            async with AsyncExitStack() as stack:
                # Register first: even a partially allocated startup must be unwound.
                stack.push_async_callback(database.shutdown)
                await database.startup()
                await verify_startup()
                for resource in (storage, *transports):
                    stack.push_async_callback(resource.shutdown)
                    await resource.startup()
                # Tasks only begin after dependencies and schema verification are ready.
                jobs: dict[str, Callable[[], Awaitable[None]]] = {}
                if database.enabled and settings.cdek_client_id and settings.cdek_client_secret:
                    jobs["pickup-directory"] = PickupDirectory(database, settings).run
                if settings.tochka_payouts_enabled and bank_payout_service is not None:
                    jobs["bank-payout-reconciliation"] = lambda: reconcile_bank_payouts(
                        database, bank_payout_service
                    )
                for name, job in jobs.items():
                    task = asyncio.create_task(job(), name=name)
                    task.add_done_callback(_report_task_exit)
                    tasks[name] = task
                    stack.push_async_callback(_stop_task, task)
                logger.info("Application ready", extra={"event": "runtime.ready"})
                yield
        except Exception:
            logger.exception("Application lifecycle failed", extra={"event": "runtime.failed"})
            raise
        finally:
            logger.info("Application stopped", extra={"event": "runtime.stopped"})

    return lifespan
