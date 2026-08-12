from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

from sqlalchemy.engine import make_url

from app.core.exceptions import ConfigurationError

ORDER_COLUMNS = (
    "id",
    "email",
    "phone",
    "first_name",
    "last_name",
    "patronymic",
    "delivery_city",
    "delivery_method",
    "delivery_address",
    "payment_method",
    "cart_items",
    "total_price",
    "status",
    "cdek_uuid",
    "cdek_point_code",
    "delivery_price",
    "payment_id",
    "payment_status",
    "created_at",
    "cdek_number",
    "cdek_status",
)


class LegacyOrderReader:
    """Read the transitional SQLite order source without allowing writes."""

    def __init__(self, database_url: str) -> None:
        url = make_url(database_url)
        if not url.drivername.startswith("sqlite") or not url.database:
            raise ConfigurationError("Legacy order bridge requires a file-backed SQLite URL")
        if url.database == ":memory:":
            raise ConfigurationError("Legacy order bridge does not support in-memory SQLite")
        self.database_path = Path(url.database).expanduser().resolve()

    def validate(self) -> None:
        with closing(self._connect()) as connection:
            available = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(orders)").fetchall()
            }
        missing = sorted(set(ORDER_COLUMNS) - available)
        if missing:
            raise ConfigurationError("Legacy orders schema is incompatible: " + ", ".join(missing))

    def find_order_ids_by_verified_email(self, normalized_email: str) -> list[int]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT id FROM orders "
                "WHERE email IS NOT NULL AND lower(trim(email)) = ? "
                "ORDER BY id DESC",
                (normalized_email,),
            ).fetchall()
        return [int(row["id"]) for row in rows]

    def get_orders(self, order_ids: Sequence[int]) -> list[dict[str, object]]:
        unique_ids = sorted({int(order_id) for order_id in order_ids if order_id > 0})
        if not unique_ids:
            return []
        rows: list[sqlite3.Row] = []
        with closing(self._connect()) as connection:
            for chunk in _chunks(unique_ids, size=500):
                placeholders = ",".join("?" for _ in chunk)
                rows.extend(
                    connection.execute(
                        f"SELECT {', '.join(ORDER_COLUMNS)} FROM orders "  # noqa: S608
                        f"WHERE id IN ({placeholders}) ORDER BY id DESC",
                        chunk,
                    ).fetchall()
                )
        return [dict(row) for row in sorted(rows, key=lambda row: int(row["id"]), reverse=True)]

    def _connect(self) -> sqlite3.Connection:
        uri = f"file:{quote(str(self.database_path), safe='/')}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=5)
        except sqlite3.Error as error:
            raise ConfigurationError("Legacy order database is unavailable") from error
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection


def _chunks(values: Sequence[int], *, size: int) -> Iterator[tuple[int, ...]]:
    for start in range(0, len(values), size):
        yield tuple(values[start : start + size])
