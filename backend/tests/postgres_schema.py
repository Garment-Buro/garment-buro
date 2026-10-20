import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text


async def seed_historical_product(
    connection, *, title: str, price: int = 80, stock_quantity: int = 0
) -> int:
    """Seed older schemas without importing future ORM columns or defaults."""
    return await connection.scalar(
        text(
            "INSERT INTO products (title,price,sizes,colors,stock_quantity) "
            "VALUES (:title,:price,'[\"M\"]','[\"white\"]',:stock) RETURNING id"
        ),
        {"title": title, "price": price, "stock": stock_quantity},
    )


async def seed_historical_landing(
    connection, *, partner_id: int, slug: str, description: str
) -> int:
    """Insert the pre-version schema without ORM defaults from a later migration."""
    return await connection.scalar(
        text(
            "INSERT INTO partner_landings "
            "(partner_id,slug,title,headline,description,cta_label,cta_href,content) "
            "VALUES (:partner_id,:slug,'Historical collection','Collection',:description,'Open','/','{}') "
            "RETURNING id"
        ),
        {"partner_id": partner_id, "slug": slug, "description": description},
    )


def migrate(url, *command):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *command],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, APP_ENV="test", DATABASE_ENABLED="true", DATABASE_URL=url),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr or result.stdout
