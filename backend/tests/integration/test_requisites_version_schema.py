"""Adding optimistic versions never rewrites historical encrypted bank documents."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.identity.models import User
from app.modules.partners.models import PartnerProfile
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_bank_version_upgrade_and_rollback_preserve_ciphertext(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20261018_0071")
    owned = {}
    original = None

    async def action(name):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                if name == "seed":
                    owned["user"] = await connection.scalar(
                        insert(User).values(internal_identity=uuid4().hex).returning(User.id)
                    )
                    owned["partner"] = await connection.scalar(
                        insert(PartnerProfile)
                        .values(
                            user_id=owned["user"],
                            code=uuid4().hex,
                            display_name="Historical bank owner",
                            commission_bps=1000,
                        )
                        .returning(PartnerProfile.id)
                    )
                    # Raw SQL intentionally targets the historical schema without version.
                    await connection.execute(
                        text(
                            "INSERT INTO partner_requisites(partner_id,ciphertext,nonce,tag,key_version,schema_version,payload_sha256) VALUES (:id,:cipher,:nonce,:tag,1,1,:hash)"
                        ),
                        {
                            "id": owned["partner"],
                            "cipher": "historical encrypted bytes",
                            "nonce": "nonce",
                            "tag": "tag",
                            "hash": "a" * 64,
                        },
                    )
                if name == "cleanup":
                    await connection.execute(
                        text("DELETE FROM partner_profiles WHERE id=:id"),
                        {"id": owned.get("partner")},
                    )
                    await connection.execute(
                        text("DELETE FROM users WHERE id=:id"), {"id": owned.get("user")}
                    )
                    return
                row = (
                    await connection.execute(
                        text(
                            "SELECT ciphertext,nonce,tag,key_version,schema_version,payload_sha256,updated_at FROM partner_requisites WHERE partner_id=:id"
                        ),
                        {"id": owned["partner"]},
                    )
                ).one()
                if name == "seed":
                    return tuple(row)
                assert tuple(row) == original
                if name == "verify":
                    assert (
                        await connection.scalar(
                            text("SELECT version FROM partner_requisites WHERE partner_id=:id"),
                            {"id": owned["partner"]},
                        )
                        == 1
                    )
                    with pytest.raises(IntegrityError):
                        async with connection.begin_nested():
                            await connection.execute(
                                text(
                                    "UPDATE partner_requisites SET version=0 WHERE partner_id=:id"
                                ),
                                {"id": owned["partner"]},
                            )
                    await connection.execute(
                        text("UPDATE partner_requisites SET version=3 WHERE partner_id=:id"),
                        {"id": owned["partner"]},
                    )
                elif name == "down":
                    assert (
                        await connection.scalar(
                            text(
                                "SELECT count(*) FROM information_schema.columns WHERE table_name='partner_requisites' AND column_name='version'"
                            )
                        )
                        == 0
                    )
        finally:
            await engine.dispose()

    try:
        original = asyncio.run(action("seed"))
        for _ in range(2):
            migrate(postgres_url, "upgrade", "head")
            asyncio.run(action("verify"))
            migrate(postgres_url, "downgrade", "20261018_0071")
            asyncio.run(action("down"))
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("cleanup"))
