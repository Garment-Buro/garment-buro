import base64
import hashlib
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.directory_repository import ReferenceDirectoryRepository
from app.modules.crm.directory_schemas import (
    FabricDirectoryPage,
    FabricDirectoryQuery,
    FabricRequirementCard,
    FabricRequirementPage,
    ModelDirectoryCard,
    ModelDirectoryPage,
    ModelDirectoryQuery,
    ReferencePosition,
    SelectedReference,
)
from app.modules.crm.read_schemas import CrmFabricRead, CrmMaterialBalanceRead
from app.modules.crm.reference_schemas import GARMENT_MODEL_SIZE_LIMIT, CrmGarmentModelReferenceRead
from app.modules.identity.security import ensure_utc


class InvalidReferenceCursor(ValueError):
    pass


class ModelEditorSizeLimit(ValueError):
    pass


def fingerprint(query):
    return hashlib.sha256(query.model_dump_json(exclude={"cursor", "limit"}).encode()).hexdigest()


def position(query, kind):
    if query.cursor is None:
        return None, None
    try:
        row = ReferencePosition.model_validate_json(
            base64.b64decode(query.cursor, altchars=b"-_", validate=True)
        )
        if row.kind != kind or row.filters != fingerprint(query):
            raise ValueError("Different directory or filters")
        if kind == "fabric-requirements":
            if row.value != str(row.id):
                raise ValueError("Invalid requirement position")
            return row.id, row.id
        field = query.sort.split(":")[0]
        if field in {"name", "code", "model"}:
            return row.id, row.value
        value = Decimal(row.value)
        if not value.is_finite() or abs(value) > Decimal("999999999999999"):
            raise ValueError("Invalid number")
        if field in {
            "sizes",
            "products",
            "stock",
            "capacity",
            "priority",
            "id",
            "revision",
            "position",
        } and (value < 0 or value != value.to_integral_value()):
            raise ValueError("Invalid count")
        if field == "id" and value != row.id:
            raise ValueError("Invalid ID position")
        if field == "price" and value < 0:
            raise ValueError("Invalid price")
        return row.id, value
    except (ValueError, ValidationError, InvalidOperation) as error:
        raise InvalidReferenceCursor("Invalid reference cursor") from error


def continuation(records, query, kind):
    if len(records) <= query.limit:
        return None
    row = records[query.limit - 1]
    return base64.urlsafe_b64encode(
        ReferencePosition(
            version=1,
            kind=kind,
            id=row["id"],
            value=str(row["order_value"]),
            filters=fingerprint(query),
        )
        .model_dump_json()
        .encode()
    ).decode()


class ReferenceDirectoryService:
    repository = ReferenceDirectoryRepository()

    async def models(self, session: AsyncSession, query: ModelDirectoryQuery):
        after_id, after_value = position(query, "models")
        rows = await self.repository.models(
            session, query, after_id=after_id, after_value=after_value
        )
        return ModelDirectoryPage(
            items=[ModelDirectoryCard.model_validate(row) for row in rows[: query.limit]],
            next_cursor=continuation(rows, query, "models"),
        )

    async def fabrics(self, session: AsyncSession, query: FabricDirectoryQuery):
        after_id, after_value = position(query, "fabrics")
        rows = await self.repository.fabrics(
            session, query, after_id=after_id, after_value=after_value
        )
        items = []
        for row in rows[: query.limit]:
            balance = (
                CrmMaterialBalanceRead(
                    on_hand_meters=row["on_hand_meters"],
                    reserved_meters=row["reserved_meters"],
                    available_meters=row["on_hand_meters"] - row["reserved_meters"],
                    version=row["balance_version"],
                    updated_at=ensure_utc(row["balance_updated_at"]),
                )
                if row["balance_id"] is not None
                else None
            )
            items.append(CrmFabricRead.model_validate({**row, "balance": balance}))
        return FabricDirectoryPage(items=items, next_cursor=continuation(rows, query, "fabrics"))

    async def model(self, session: AsyncSession, model_id: int):
        row = await self.repository.model_detail(session, model_id)
        if row is not None and len(row["sizes"]) > GARMENT_MODEL_SIZE_LIMIT:
            raise ModelEditorSizeLimit(
                f"У модели больше {GARMENT_MODEL_SIZE_LIMIT} активных размеров. Нужна проверка размерной сетки."
            )
        return CrmGarmentModelReferenceRead.model_validate(row) if row is not None else None

    async def selected(self, session: AsyncSession, query):
        return [
            SelectedReference.model_validate(row)
            for row in await self.repository.selected(session, query.kind, query.ids)
        ]

    async def fabric_requirements(self, session: AsyncSession, query):
        after_id, _ = position(query, "fabric-requirements")
        rows = await self.repository.fabric_requirements(session, query, after_id)
        return FabricRequirementPage(
            items=[FabricRequirementCard.model_validate(row) for row in rows[: query.limit]],
            next_cursor=continuation(rows, query, "fabric-requirements"),
        )
