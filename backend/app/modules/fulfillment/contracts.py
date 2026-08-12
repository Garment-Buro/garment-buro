from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fulfillment.models import FulfillmentJob, FulfillmentJobKind

SAFE_FULFILLMENT_CODE = re.compile(r"^[a-z0-9_.-]{1,64}$")
SAFE_FULFILLMENT_REFERENCE = re.compile(r"^[A-Za-z0-9:._-]{1,255}$")


class FulfillmentHandlerError(RuntimeError):
    def __init__(self, code: str, *, permanent: bool) -> None:
        if not SAFE_FULFILLMENT_CODE.fullmatch(code):
            raise ValueError("Fulfillment handler error code is not safe")
        super().__init__(code)
        self.code = code
        self.permanent = permanent


class FulfillmentHandler(Protocol):
    """A database-only handoff. Implementations must not perform network I/O."""

    kind: FulfillmentJobKind

    async def prepare(
        self,
        session: AsyncSession,
        job: FulfillmentJob,
        *,
        now: datetime,
    ) -> object: ...

    async def apply(
        self,
        session: AsyncSession,
        job: FulfillmentJob,
        prepared: object,
        *,
        now: datetime,
    ) -> str | None: ...
