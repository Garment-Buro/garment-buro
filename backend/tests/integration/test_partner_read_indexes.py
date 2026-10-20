"""Read indexes can be rolled back without touching profiles or money rows."""

import asyncio
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.identity.models import User
from app.modules.partners.models import PartnerPayoutRequest, PartnerProfile
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_partner_read_index_upgrade_and_downgrade_preserve_money(postgres_url):
    owned = {}
    indexes = {"ix_partner_profiles_status_id", "ix_partner_payouts_owner_recent"}

    async def action(name, present=True):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                if name == "seed":
                    owned["user"] = await connection.scalar(
                        insert(User).values(internal_identity=uuid4().hex).returning(User.id)
                    )
                    owned["profile"] = await connection.scalar(
                        insert(PartnerProfile)
                        .values(
                            user_id=owned["user"],
                            code=uuid4().hex,
                            display_name="Existing owner",
                            commission_bps=1000,
                            status="active",
                        )
                        .returning(PartnerProfile.id)
                    )
                    owned["payout"] = await connection.scalar(
                        insert(PartnerPayoutRequest)
                        .values(
                            partner_id=owned["profile"],
                            amount=Decimal("10.01"),
                            status="paid",
                            note="Keep existing note",
                        )
                        .returning(PartnerPayoutRequest.id)
                    )
                elif name == "verify":
                    names = set(
                        await connection.scalars(
                            text(
                                "SELECT indexname FROM pg_indexes WHERE schemaname=current_schema()"
                            )
                        )
                    )
                    assert (indexes <= names) if present else not indexes.intersection(names)
                    assert (
                        await connection.execute(
                            select(
                                PartnerPayoutRequest.amount,
                                PartnerPayoutRequest.status,
                                PartnerPayoutRequest.note,
                            ).where(PartnerPayoutRequest.id == owned["payout"])
                        )
                    ).one() == (Decimal("10.01"), "paid", "Keep existing note")
                    assert (
                        await connection.scalar(
                            select(PartnerProfile.display_name).where(
                                PartnerProfile.id == owned["profile"]
                            )
                        )
                        == "Existing owner"
                    )
                else:
                    await connection.execute(
                        delete(PartnerPayoutRequest).where(
                            PartnerPayoutRequest.id == owned.get("payout")
                        )
                    )
                    await connection.execute(
                        delete(PartnerProfile).where(PartnerProfile.id == owned.get("profile"))
                    )
                    await connection.execute(delete(User).where(User.id == owned.get("user")))
        finally:
            await engine.dispose()

    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20261018_0070")
    try:
        asyncio.run(action("seed"))
        asyncio.run(action("verify", False))
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("verify"))
        migrate(postgres_url, "downgrade", "20261018_0070")
        asyncio.run(action("verify", False))
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("cleanup"))
