"""Daily atomic snapshots. Searches never call the shipping provider."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import aiohttp
from sqlalchemy import delete, or_, select, update

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.modules.delivery.directory_models import PickupDirectoryState, PickupPoint
from app.modules.delivery.provider import AiohttpCdekTransport, CdekProviderError

logger = logging.getLogger(__name__)
DIRECTORY_KEY = "cdek-ru"
REFRESH_INTERVAL = timedelta(days=1)
RETRY_INTERVAL = timedelta(minutes=15)


def normalize_points(raw: object) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("Empty or invalid CDEK directory")
    points = {}
    for item in raw:
        if not isinstance(item, dict) or not item.get("code"):
            raise ValueError("Invalid pickup point")
        location = item.get("location") or {}
        if not location.get("city") or not location.get("address"):
            raise ValueError("Missing pickup address")
        code = str(item["code"])
        payload = {key: item.get(key) for key in ("name", "work_time", "type", "note")}
        payload.update(code=code, location={key: location.get(key) for key in (
            "city", "city_code", "region", "address", "address_full", "latitude", "longitude",
        )})
        search_text = " ".join(str(value or "") for value in (
            code, item.get("name"), location.get("region"), location.get("city"),
            location.get("address"),
        )).casefold().replace("ё", "е")
        points[code] = {"code": code, "search_text": search_text, "payload": payload}
    return list(points.values())


class DirectoryTransport(AiohttpCdekTransport):
    async def fetch_points(self) -> object:
        token = await self._access_token()
        session = await self._require_session()
        async with session.get(
            f"{self.base_url}/deliverypoints",
            params={"country_code": "RU", "type": "PVZ"},
            headers={"Authorization": f"Bearer {token}"},
            allow_redirects=False,
        ) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                body.extend(chunk)
                if len(body) > 64 * 1024 * 1024:
                    raise ValueError("CDEK directory exceeds size limit")
            import json
            return json.loads(body)


class PickupDirectory:
    def __init__(self, database: DatabaseManager, settings: Settings) -> None:
        self.database = database
        self.settings = settings

    async def refresh(self) -> bool:
        now = datetime.now(UTC)
        # Atomic lease also throttles provider failures across all API replicas.
        async with self.database.session() as session:
            result = await session.execute(update(PickupDirectoryState).where(
                PickupDirectoryState.key == DIRECTORY_KEY,
                or_(PickupDirectoryState.updated_at.is_(None),
                    PickupDirectoryState.updated_at < now - REFRESH_INTERVAL),
                or_(PickupDirectoryState.retry_at.is_(None),
                    PickupDirectoryState.retry_at < now),
            ).values(retry_at=now + RETRY_INTERVAL))
            await session.commit()
            if not result.rowcount:
                return False
        transport = DirectoryTransport(self.settings)
        try:
            points = normalize_points(await transport.fetch_points())
            async with self.database.session() as session:
                # A failed fetch/parse never deletes the last good snapshot.
                await session.execute(delete(PickupPoint))
                for start in range(0, len(points), 500):
                    session.add_all(PickupPoint(**point) for point in points[start:start + 500])
                    await session.flush()
                await session.execute(update(PickupDirectoryState).where(
                    PickupDirectoryState.key == DIRECTORY_KEY,
                ).values(updated_at=now, retry_at=None))
                await session.commit()
            return True
        finally:
            await transport.shutdown()

    async def run(self) -> None:
        while True:
            try:
                await self.refresh()
            except (CdekProviderError, aiohttp.ClientError, ValueError, TimeoutError):
                logger.warning("CDEK directory refresh unavailable; retaining last snapshot")
            except Exception:  # noqa: BLE001 - background job must survive storage outages
                logger.exception("Pickup directory storage unavailable")
            await asyncio.sleep(60)


def search_statement(query: str):
    statement = select(PickupPoint)
    for token in query.casefold().replace("ё", "е").split()[:8]:
        statement = statement.where(PickupPoint.search_text.contains(token, autoescape=True))
    return statement.order_by(PickupPoint.code)
