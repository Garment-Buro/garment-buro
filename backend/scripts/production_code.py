"""Issue/revoke a personal code for an existing, explicitly selected employee."""

import argparse
import asyncio
import sys

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.production.auth_service import PREFIXES, issue_code, revoke_code


async def run(args):
    if not sys.stdout.isatty():
        raise ValueError("Run in an interactive terminal; never redirect employee codes to logs")
    settings = get_settings()
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            if args.revoke:
                await revoke_code(session, user_id=args.user_id)
                code = None
            else:
                code = await issue_code(
                    session,
                    user_id=args.user_id,
                    station=args.station,
                    pepper=settings.require_secret("identity_otp_pepper", "IDENTITY_OTP_PEPPER"),
                )
            await session.commit()
            print(
                f"Employee {args.user_id}: "
                + (f"new personal code {code}" if code else "code revoked")
            )
    finally:
        await database.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--station", choices=PREFIXES)
    mode.add_argument("--revoke", action="store_true")
    asyncio.run(run(parser.parse_args()))
