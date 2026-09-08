from app.modules.identity.models import PermissionCode
from app.modules.identity.repository import IdentityRepository
from app.modules.production.schemas import STATIONS


class ProductionDenied(PermissionError):
    pass


async def stations_for_user(session, user_id: int) -> list[str]:
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


def require_station(stations, station, *, supervisor=True):
    if station not in stations and not (supervisor and "tech" in stations):
        raise ProductionDenied("Это действие доступно только сотруднику своего участка")
