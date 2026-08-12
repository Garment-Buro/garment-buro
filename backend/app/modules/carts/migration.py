from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.carts.models import CartMigrationRun
from app.modules.carts.repository import CartRepository
from app.modules.carts.schemas import CartUpdateRequest
from app.modules.carts.security import digest_cart_id, normalize_cart_id
from app.modules.carts.service import CartService

LEGACY_CART_PREFIX = "cart:session:"


class CartMigrationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LegacyCartSourceEntry:
    payload: str | bytes | None
    remaining_ttl_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class LegacyCartRecord:
    cart_id: str
    payload: CartUpdateRequest
    remaining_ttl_seconds: int | None = None

    @property
    def token_digest_sha256(self) -> str:
        return digest_cart_id(self.cart_id)


@dataclass(frozen=True, slots=True)
class CartMigrationPlan:
    records: tuple[LegacyCartRecord, ...]
    fingerprint: str

    @property
    def items_count(self) -> int:
        return sum(len(record.payload.items) for record in self.records)

    def report(self) -> dict[str, object]:
        return {
            "valid": True,
            "fingerprint_sha256": self.fingerprint,
            "carts_count": len(self.records),
            "items_count": self.items_count,
        }


class LegacyCartPlanner:
    def build(
        self,
        entries: Mapping[str, str | bytes | None | LegacyCartSourceEntry],
    ) -> CartMigrationPlan:
        records: list[LegacyCartRecord] = []
        try:
            for key, source in entries.items():
                if isinstance(source, LegacyCartSourceEntry):
                    value = source.payload
                    remaining_ttl_seconds = source.remaining_ttl_seconds
                else:
                    value = source
                    remaining_ttl_seconds = None
                if not key.startswith(LEGACY_CART_PREFIX) or value is None:
                    raise CartMigrationError("Legacy cart snapshot contains an invalid entry")
                if remaining_ttl_seconds is not None and remaining_ttl_seconds <= 0:
                    raise CartMigrationError("Legacy cart snapshot has no active expiry")
                cart_id = normalize_cart_id(key.removeprefix(LEGACY_CART_PREFIX))
                if isinstance(value, bytes):
                    value = value.decode("utf-8")
                raw = json.loads(value)
                if not isinstance(raw, dict):
                    raise CartMigrationError("Legacy cart payload must be an object")
                payload = CartUpdateRequest.model_validate(raw)
                if not payload.updated_at_ms:
                    raise CartMigrationError(
                        "Legacy cart snapshot has no positive update timestamp"
                    )
                records.append(
                    LegacyCartRecord(
                        cart_id=cart_id,
                        payload=payload,
                        remaining_ttl_seconds=remaining_ttl_seconds,
                    )
                )
        except (UnicodeError, json.JSONDecodeError, ValueError) as error:
            if isinstance(error, CartMigrationError):
                raise
            raise CartMigrationError("Legacy cart snapshot is invalid") from error
        records.sort(key=lambda record: record.token_digest_sha256)
        canonical = [
            {
                "token_digest_sha256": record.token_digest_sha256,
                "payload": record.payload.model_dump(mode="json"),
            }
            for record in records
        ]
        # Remaining TTL decays between the reviewed scan and apply. Bind the
        # fingerprint to identity and content, then preserve the fresh apply TTL.
        fingerprint = hashlib.sha256(
            json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return CartMigrationPlan(tuple(records), fingerprint)


@dataclass(frozen=True, slots=True)
class CartMigrationResult:
    fingerprint_sha256: str
    carts: int
    items: int


class CartMigrationService:
    def __init__(
        self,
        settings: Settings,
        repository: CartRepository | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or CartRepository()

    async def apply(
        self,
        session: AsyncSession,
        plan: CartMigrationPlan,
        *,
        now: datetime | None = None,
    ) -> CartMigrationResult:
        existing_run = await session.scalar(
            select(CartMigrationRun).where(CartMigrationRun.fingerprint_sha256 == plan.fingerprint)
        )
        if existing_run is not None:
            return CartMigrationResult(
                existing_run.fingerprint_sha256,
                existing_run.carts_count,
                existing_run.items_count,
            )
        if any(
            record.remaining_ttl_seconds is not None
            and record.remaining_ttl_seconds > self.settings.cart_cache_ttl_seconds
            for record in plan.records
        ):
            raise CartMigrationError("Legacy cart TTL exceeds configured retention")
        counts = await self.repository.target_counts(session)
        if any(counts.values()):
            rendered = ", ".join(f"{name}={count}" for name, count in counts.items())
            raise CartMigrationError(f"Target cart storage must be empty ({rendered})")

        service = CartService(self.settings, self.repository)
        migration_time = now or datetime.now(timezone.utc)
        for record in plan.records:
            await service.import_legacy_snapshot(
                session,
                cart_id=record.cart_id,
                payload=record.payload,
                remaining_ttl_seconds=record.remaining_ttl_seconds,
                now=migration_time,
            )
        session.add(
            CartMigrationRun(
                fingerprint_sha256=plan.fingerprint,
                carts_count=len(plan.records),
                items_count=plan.items_count,
            )
        )
        await session.flush()
        return CartMigrationResult(
            plan.fingerprint,
            len(plan.records),
            plan.items_count,
        )
