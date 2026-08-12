from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.material_models import (
    CrmMaterialBalance,
    CrmMaterialMovement,
    CrmMaterialMovementType,
    CrmMaterialReservation,
    CrmMaterialReservationStatus,
)
from app.modules.crm.material_repository import CrmMaterialRepository
from app.modules.crm.service import CRM_REASON_CODE_PATTERN
from app.modules.identity.security import ensure_utc

METER_QUANTUM = Decimal("0.001")
MAX_METERS = Decimal("99999999999.999")


class CrmMaterialNotFoundError(LookupError):
    pass


class CrmMaterialConflictError(ValueError):
    pass


class CrmMaterialService:
    def __init__(self, repository: CrmMaterialRepository | None = None) -> None:
        self.repository = repository or CrmMaterialRepository()

    async def receive(
        self,
        session: AsyncSession,
        *,
        fabric_id: int,
        quantity_meters: Decimal,
        idempotency_key: str,
        reason_code: str,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmMaterialMovement:
        return await self._change_unreserved(
            session,
            fabric_id=fabric_id,
            quantity_meters=quantity_meters,
            idempotency_key=idempotency_key,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            movement_type=CrmMaterialMovementType.RECEIPT,
            now=now,
        )

    async def adjust(
        self,
        session: AsyncSession,
        *,
        fabric_id: int,
        quantity_meters: Decimal,
        direction: str,
        idempotency_key: str,
        reason_code: str,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmMaterialMovement:
        movement_type = {
            "in": CrmMaterialMovementType.ADJUSTMENT_IN,
            "out": CrmMaterialMovementType.ADJUSTMENT_OUT,
        }.get(direction)
        if movement_type is None:
            raise CrmMaterialConflictError("Material adjustment direction must be in or out")
        return await self._change_unreserved(
            session,
            fabric_id=fabric_id,
            quantity_meters=quantity_meters,
            idempotency_key=idempotency_key,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            movement_type=movement_type,
            now=now,
        )

    async def reserve(
        self,
        session: AsyncSession,
        *,
        plan_revision_id: int,
        fabric_id: int,
        quantity_meters: Decimal,
        idempotency_key: str,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> tuple[CrmMaterialReservation, CrmMaterialMovement]:
        quantity = self._quantity(quantity_meters)
        occurred_at = self._now(now)
        key_digest = self._key_digest(idempotency_key)
        command = self._command_digest(
            "reserve", plan_revision_id, fabric_id, self._decimal(quantity)
        )
        await self._require_active_fabric(session, fabric_id)
        balance = await self.repository.acquire_balance(
            session, fabric_id=fabric_id, now=occurred_at
        )
        replay = await self._replay(session, fabric_id, key_digest, command)
        if replay is not None:
            assert replay.reservation_id is not None
            reservation = await self.repository.get_reservation_for_update(
                session, reservation_id=replay.reservation_id
            )
            if reservation is None:
                raise RuntimeError("Material movement reservation is missing")
            return reservation, replay
        if (
            await self.repository.get_reservable_plan(session, plan_revision_id=plan_revision_id)
            is None
        ):
            raise CrmMaterialConflictError("Reservable production plan is required")
        existing = await self.repository.get_plan_fabric_reservation(
            session,
            plan_revision_id=plan_revision_id,
            fabric_id=fabric_id,
        )
        if existing is not None:
            raise CrmMaterialConflictError("Production plan already has a fabric reservation")
        if balance.on_hand_meters - balance.reserved_meters < quantity:
            raise CrmMaterialConflictError("Insufficient available fabric")
        reservation = CrmMaterialReservation(
            production_plan_revision_id=plan_revision_id,
            fabric_id=fabric_id,
            requested_meters=quantity,
            remaining_meters=quantity,
            consumed_meters=Decimal("0"),
            released_meters=Decimal("0"),
            status=CrmMaterialReservationStatus.ACTIVE.value,
            version=1,
            created_by_user_id=actor_user_id,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        session.add(reservation)
        await session.flush()
        balance.reserved_meters += quantity
        self._touch_balance(balance, occurred_at)
        movement = self._movement(
            balance,
            reservation_id=reservation.id,
            movement_type=CrmMaterialMovementType.RESERVE,
            quantity=quantity,
            key_digest=key_digest,
            command_digest=command,
            reason_code="production_reserved",
            actor_user_id=actor_user_id,
            occurred_at=occurred_at,
        )
        session.add(movement)
        await session.flush()
        return reservation, movement

    async def release(
        self,
        session: AsyncSession,
        *,
        reservation_id: int,
        quantity_meters: Decimal,
        idempotency_key: str,
        reason_code: str,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmMaterialMovement:
        return await self._close_reservation_quantity(
            session,
            reservation_id=reservation_id,
            quantity_meters=quantity_meters,
            idempotency_key=idempotency_key,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            movement_type=CrmMaterialMovementType.RELEASE,
            now=now,
        )

    async def consume(
        self,
        session: AsyncSession,
        *,
        reservation_id: int,
        quantity_meters: Decimal,
        idempotency_key: str,
        reason_code: str,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmMaterialMovement:
        return await self._close_reservation_quantity(
            session,
            reservation_id=reservation_id,
            quantity_meters=quantity_meters,
            idempotency_key=idempotency_key,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            movement_type=CrmMaterialMovementType.CONSUME,
            now=now,
        )

    async def _change_unreserved(
        self,
        session: AsyncSession,
        *,
        fabric_id: int,
        quantity_meters: Decimal,
        idempotency_key: str,
        reason_code: str,
        actor_user_id: int | None,
        movement_type: CrmMaterialMovementType,
        now: datetime | None,
    ) -> CrmMaterialMovement:
        self._reason(reason_code)
        quantity = self._quantity(quantity_meters)
        occurred_at = self._now(now)
        key_digest = self._key_digest(idempotency_key)
        command = self._command_digest(
            movement_type.value, fabric_id, self._decimal(quantity), reason_code
        )
        await self._require_active_fabric(session, fabric_id)
        balance = await self.repository.acquire_balance(
            session, fabric_id=fabric_id, now=occurred_at
        )
        replay = await self._replay(session, fabric_id, key_digest, command)
        if replay is not None:
            return replay
        if movement_type in {
            CrmMaterialMovementType.RECEIPT,
            CrmMaterialMovementType.ADJUSTMENT_IN,
        }:
            balance.on_hand_meters += quantity
        else:
            if balance.on_hand_meters - balance.reserved_meters < quantity:
                raise CrmMaterialConflictError("Adjustment would consume reserved fabric")
            balance.on_hand_meters -= quantity
        self._touch_balance(balance, occurred_at)
        movement = self._movement(
            balance,
            reservation_id=None,
            movement_type=movement_type,
            quantity=quantity,
            key_digest=key_digest,
            command_digest=command,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            occurred_at=occurred_at,
        )
        session.add(movement)
        await session.flush()
        return movement

    async def _close_reservation_quantity(
        self,
        session: AsyncSession,
        *,
        reservation_id: int,
        quantity_meters: Decimal,
        idempotency_key: str,
        reason_code: str,
        actor_user_id: int | None,
        movement_type: CrmMaterialMovementType,
        now: datetime | None,
    ) -> CrmMaterialMovement:
        self._reason(reason_code)
        quantity = self._quantity(quantity_meters)
        reservation = await self.repository.get_reservation_for_update(
            session, reservation_id=reservation_id
        )
        if reservation is None:
            raise CrmMaterialNotFoundError("CRM material reservation was not found")
        occurred_at = self._now(now)
        key_digest = self._key_digest(idempotency_key)
        command = self._command_digest(
            movement_type.value,
            reservation_id,
            reservation.fabric_id,
            self._decimal(quantity),
            reason_code,
        )
        balance = await self.repository.acquire_balance(
            session, fabric_id=reservation.fabric_id, now=occurred_at
        )
        replay = await self._replay(session, reservation.fabric_id, key_digest, command)
        if replay is not None:
            return replay
        if reservation.remaining_meters < quantity:
            raise CrmMaterialConflictError("Material reservation remaining quantity is too small")
        if (
            movement_type == CrmMaterialMovementType.CONSUME
            and await self.repository.get_active_plan(
                session, plan_revision_id=reservation.production_plan_revision_id
            )
            is None
        ):
            raise CrmMaterialConflictError("Cannot consume fabric for a superseded plan")
        reservation.remaining_meters -= quantity
        balance.reserved_meters -= quantity
        if movement_type == CrmMaterialMovementType.CONSUME:
            reservation.consumed_meters += quantity
            balance.on_hand_meters -= quantity
        else:
            reservation.released_meters += quantity
        if reservation.remaining_meters == 0:
            reservation.status = CrmMaterialReservationStatus.CLOSED.value
        reservation.version += 1
        reservation.updated_at = occurred_at
        self._touch_balance(balance, occurred_at)
        movement = self._movement(
            balance,
            reservation_id=reservation.id,
            movement_type=movement_type,
            quantity=quantity,
            key_digest=key_digest,
            command_digest=command,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            occurred_at=occurred_at,
        )
        session.add(movement)
        await session.flush()
        return movement

    async def _require_active_fabric(self, session: AsyncSession, fabric_id: int) -> None:
        if await self.repository.get_active_fabric(session, fabric_id=fabric_id) is None:
            raise CrmMaterialNotFoundError("Active CRM fabric was not found")

    async def _replay(
        self,
        session: AsyncSession,
        fabric_id: int,
        key_digest: str,
        command_digest: str,
    ) -> CrmMaterialMovement | None:
        movement = await self.repository.get_movement(
            session, fabric_id=fabric_id, key_sha256=key_digest
        )
        if movement is not None and movement.command_sha256 != command_digest:
            raise CrmMaterialConflictError("Material idempotency key was reused")
        return movement

    @staticmethod
    def _movement(
        balance: CrmMaterialBalance,
        *,
        reservation_id: int | None,
        movement_type: CrmMaterialMovementType,
        quantity: Decimal,
        key_digest: str,
        command_digest: str,
        reason_code: str,
        actor_user_id: int | None,
        occurred_at: datetime,
    ) -> CrmMaterialMovement:
        return CrmMaterialMovement(
            fabric_id=balance.fabric_id,
            reservation_id=reservation_id,
            movement_type=movement_type.value,
            quantity_meters=quantity,
            balance_on_hand_after=balance.on_hand_meters,
            balance_reserved_after=balance.reserved_meters,
            idempotency_key_sha256=key_digest,
            command_sha256=command_digest,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _touch_balance(balance: CrmMaterialBalance, now: datetime) -> None:
        balance.version += 1
        balance.updated_at = now

    @staticmethod
    def _quantity(value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > MAX_METERS:
            raise CrmMaterialConflictError("Material quantity is out of range")
        quantized = value.quantize(METER_QUANTUM)
        if quantized != value:
            raise CrmMaterialConflictError("Material quantity supports at most 3 decimals")
        return quantized

    @staticmethod
    def _reason(value: str) -> None:
        if not CRM_REASON_CODE_PATTERN.fullmatch(value):
            raise CrmMaterialConflictError("Material reason code has an invalid format")

    @staticmethod
    def _key_digest(value: str) -> str:
        if not value or len(value) > 255:
            raise CrmMaterialConflictError("Material idempotency key is invalid")
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def _command_digest(*values: object) -> str:
        body = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
        return hashlib.sha256(body).hexdigest()

    @staticmethod
    def _decimal(value: Decimal) -> str:
        return format(value, ".3f")

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        return ensure_utc(value or datetime.now(timezone.utc))
