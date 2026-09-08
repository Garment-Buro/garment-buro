"""Backend-only moderation and recovery. No HTTP approval endpoint."""

import argparse
import asyncio
import json

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.modules.delivery.provider import AiohttpCdekTransport, CdekProviderClient
from app.modules.delivery.recovery import recover_shipment
from app.modules.orders.workflow import OrderModerationService
from app.modules.orders.workflow_operations import inspect_orders, requeue


async def run(args):
    database = DatabaseManager(get_settings())
    await database.startup()
    try:
        async with database.session() as session:
            if args.action == "list":
                rows = await inspect_orders(
                    session, order_id=args.order_id, before_id=args.before_id, limit=args.limit
                )
                for row in rows:
                    print(json.dumps(row, ensure_ascii=False))
            elif args.action in {"approve", "reject"}:
                required(args, "order_id", "version", "actor_id", "key", "note")
                flow = await OrderModerationService(database.settings).decide(
                    session,
                    order_id=args.order_id,
                    expected_version=args.version,
                    actor_user_id=args.actor_id,
                    decision=args.action,
                    key=args.key,
                    note=args.note,
                )
                await session.commit()
                print(
                    json.dumps(
                        {"order_id": flow.order_id, "state": flow.state, "version": flow.version}
                    )
                )
            elif args.action == "requeue":
                required(args, "job_id", "generation", "actor_id")
                await requeue(
                    session,
                    family=args.family,
                    job_id=args.job_id,
                    expected_generation=args.generation,
                    actor_id=args.actor_id,
                )
                await session.commit()
                print(
                    "Requeued without changing payment/provider identity; recovery remains guarded"
                )
            elif args.action == "recover-cdek":
                required(args, "order_id", "version", "actor_id", "provider_uuid")
                transport = AiohttpCdekTransport(database.settings)
                try:
                    await transport.startup()
                    await recover_shipment(
                        session,
                        CdekProviderClient(transport),
                        order_id=args.order_id,
                        expected_version=args.version,
                        actor_id=args.actor_id,
                        provider_uuid=args.provider_uuid,
                    )
                    await session.commit()
                finally:
                    await transport.shutdown()
                print("CDEK shipment recovered by verified GET, no shipment was created")
    finally:
        await database.shutdown()


def required(args, *names):
    if any(getattr(args, name) is None for name in names):
        raise ValueError("Required arguments: " + ", ".join(names))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "approve", "reject", "requeue", "recover-cdek"))
    for name in ("order-id", "version", "actor-id", "job-id", "generation", "before-id"):
        parser.add_argument("--" + name, type=int)
    parser.add_argument(
        "--family", choices=("workflow", "fulfillment", "reconciliation"), default="workflow"
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--provider-uuid")
    parser.add_argument("--key")
    parser.add_argument("--note")
    asyncio.run(run(parser.parse_args()))
