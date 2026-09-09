"""Explicit demo provisioning. No API calls to payment, shipping, or notification providers."""

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.crm.file_service import CrmFileService
from app.modules.production.demo.employees import STATIONS, ensure_employees
from app.modules.production.demo.orders import ensure_order
from app.modules.production.demo.references import ensure_references
from app.modules.production.demo.scenarios import prepare_scenario


async def provision(database, files, credentials_file, image):
    employees = await ensure_employees(database, credentials_file)
    actor = employees["tech"]["user_id"]
    async with database.session() as session:
        product, size, card = await ensure_references(session, actor)
    orders = []
    for station, label in STATIONS.items():
        async with database.session() as session:
            order, project, unit, _ = await ensure_order(session, station, label, product, actor)
        await prepare_scenario(database, files, project, unit, station, actor, size, card, image)
        orders.append({"station": station, "order_id": order, "project_id": project})
    return orders


async def run(args):
    if not args.confirm_demo:
        raise ValueError("Explicit --confirm-demo is required")
    settings = get_settings()
    database = DatabaseManager(settings)
    await database.startup()
    storage = MinioStorage(settings)
    await storage.startup()
    try:
        # Dedicated session-level lock survives service commits and prevents concurrent seeds.
        async with database.engine.connect() as lock:
            if lock.dialect.name == "postgresql":
                await lock.execute(text("SELECT pg_advisory_lock(79328038)"))
            try:
                orders = await provision(
                    database,
                    CrmFileService(storage),
                    args.credentials_file,
                    args.reference_image.read_bytes(),
                )
                for row in orders:
                    print(row)  # IDs only, never employee codes.
                print(
                    "Demo credentials saved to the private file; existing codes and scenarios retained"
                )
            finally:
                if lock.dialect.name == "postgresql":
                    await lock.execute(text("SELECT pg_advisory_unlock(79328038)"))
    finally:
        await database.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-demo", action="store_true")
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--reference-image", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
