from sqlalchemy import select

from app.modules.identity.models import PermissionCode
from app.modules.identity.repository import IdentityRepository
from app.modules.production.auth_models import ProductionEmployee
from app.modules.production.schemas import STATIONS


class ProductionDenied(PermissionError):
    pass


async def can_administer(session, user_id: int) -> bool:
    return await IdentityRepository().user_has_permission(
        session, user_id=user_id, permission=PermissionCode.PRODUCTION_ADMIN
    )


async def stations_for_user(session, user_id: int) -> list[str]:
    availability = await session.scalar(
        select(ProductionEmployee.availability).where(ProductionEmployee.user_id == user_id)
    )
    if availability and availability != "available":
        raise ProductionDenied("Сотрудник временно отсутствует. Обратитесь к администратору")
    repository = IdentityRepository()
    if not await repository.user_has_permission(
        session, user_id=user_id, permission=PermissionCode.PRODUCTION_ACCESS
    ):
        raise ProductionDenied("Нет доступа к производству")
    return [
        station
        for station in STATIONS
        if await repository.user_has_permission(
            session, user_id=user_id, permission=PermissionCode(f"production.{station}")
        )
    ]


def require_station(stations, station, *, supervisor=False):
    if station not in stations and not (supervisor and "tech" in stations):
        raise ProductionDenied("Это действие доступно только сотруднику своего участка")
