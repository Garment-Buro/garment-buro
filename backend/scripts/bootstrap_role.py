from __future__ import annotations

import argparse
import asyncio
import json

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.identity.models import RoleName
from app.modules.identity.role_bootstrap import RoleBootstrapError, RoleBootstrapService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect or grant a privileged target role with an explicit user-ID guard",
    )
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--role",
        required=True,
        choices=[RoleName.MANAGER.value, RoleName.ADMIN.value],
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-user-id", type=int)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    if not settings.database_enabled:
        raise RoleBootstrapError("DATABASE_ENABLED is required")
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            service = RoleBootstrapService()
            plan = await service.inspect(
                session,
                email=args.email,
                role=RoleName(args.role),
            )
            if args.apply:
                if args.expect_user_id is None:
                    raise RoleBootstrapError("--expect-user-id is required with --apply")
                plan = await service.apply(
                    session,
                    plan=plan,
                    expected_user_id=args.expect_user_id,
                )
                await session.commit()
            return {
                "applied": bool(args.apply),
                "user_id": plan.user_id,
                "role": plan.role.value,
                "already_assigned": plan.already_assigned,
            }
    finally:
        await database.shutdown()


def main() -> int:
    args = parse_args()
    try:
        result = asyncio.run(run(args))
    except RoleBootstrapError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
