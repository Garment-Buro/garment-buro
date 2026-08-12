from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.carts.migration import (
    LEGACY_CART_PREFIX,
    CartMigrationError,
    CartMigrationPlan,
    CartMigrationService,
    LegacyCartPlanner,
    LegacyCartSourceEntry,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit or import active legacy Redis carts",
    )
    parser.add_argument("--redis-url")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--expect-fingerprint",
        help="Required with --apply; must equal the reviewed live snapshot",
    )
    return parser.parse_args()


def read_legacy_entries(redis_url: str) -> dict[str, LegacyCartSourceEntry]:
    client: Redis | None = None
    try:
        client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        entries: dict[str, LegacyCartSourceEntry] = {}
        for key in client.scan_iter(match=f"{LEGACY_CART_PREFIX}*", count=500):
            value = client.get(key)
            remaining_ttl_seconds = int(client.ttl(key))
            if value is None or remaining_ttl_seconds == -2:
                continue
            if remaining_ttl_seconds <= 0:
                raise CartMigrationError("Legacy Redis cart has no active expiry")
            entries[str(key)] = LegacyCartSourceEntry(
                payload=value,
                remaining_ttl_seconds=remaining_ttl_seconds,
            )
        client.ping()
        return entries
    except (RedisError, ValueError) as error:
        raise CartMigrationError("Legacy Redis cart source is unavailable") from error
    finally:
        if client is not None:
            try:
                client.close()
            except RedisError:
                pass


async def apply_plan(plan: CartMigrationPlan) -> dict[str, object]:
    settings = get_settings()
    if not settings.database_enabled:
        raise CartMigrationError("DATABASE_ENABLED is required for --apply")
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            result = await CartMigrationService(settings).apply(session, plan)
            await session.commit()
    finally:
        await database.shutdown()
    return {
        "applied": True,
        "fingerprint_sha256": result.fingerprint_sha256,
        "carts": result.carts,
        "items": result.items,
    }


def main() -> int:
    args = parse_args()
    settings = get_settings()
    try:
        entries = read_legacy_entries(args.redis_url or settings.redis_url)
        plan = LegacyCartPlanner().build(entries)
        report = plan.report()
        exit_code = 0
        if args.apply:
            if not args.expect_fingerprint:
                report["apply_error"] = "--expect-fingerprint is required with --apply"
                exit_code = 2
            elif args.expect_fingerprint != plan.fingerprint:
                report["apply_error"] = "Reviewed fingerprint does not match live Redis carts"
                exit_code = 2
            else:
                report["apply_result"] = asyncio.run(apply_plan(plan))
    except CartMigrationError as error:
        report = {"valid": False, "error": str(error)}
        exit_code = 1

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
