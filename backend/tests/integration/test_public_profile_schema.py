"""Real PostgreSQL constraints and reversible migration for opt-in public profiles."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.identity.models import User
from app.modules.media.models import MediaObject
from app.modules.partners.models import PartnerLanding, PartnerProfile
from app.modules.public_profiles.models import PublicUserProfile
from tests.postgres_schema import migrate, seed_historical_landing

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_public_profile_migration_is_opt_in_reversible_and_preserves_existing_data(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20261015_0062")
    owned = {}

    async def action(name):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                if name == "seed":
                    owned["users"] = [
                        await connection.scalar(
                            insert(User).values(internal_identity=uuid4().hex).returning(User.id)
                        )
                        for _ in range(3)
                    ]
                    owned["partner"] = await connection.scalar(
                        insert(PartnerProfile)
                        .values(
                            user_id=owned["users"][2],
                            code=uuid4().hex,
                            display_name="Historical owner",
                            commission_bps=1000,
                        )
                        .returning(PartnerProfile.id)
                    )
                    owned["landing"] = await seed_historical_landing(
                        connection,
                        partner_id=owned["partner"],
                        slug=uuid4().hex,
                        description="Preserve collection",
                    )
                elif name == "verify":
                    assert (
                        await connection.scalar(select(func.count()).select_from(PublicUserProfile))
                        == 0
                    )
                    user, other, third = owned["users"]
                    slug = "migration-" + uuid4().hex
                    values = {
                        "user_id": user,
                        "slug": slug,
                        "display_name": "Public name",
                        "bio": "Public bio",
                    }
                    identity = await connection.scalar(
                        insert(PublicUserProfile).values(**values).returning(PublicUserProfile.id)
                    )
                    for changes in (
                        {"slug": "second-address"},
                        {"user_id": other},
                        {"user_id": third, "slug": "new-address", "version": 0},
                        {"user_id": third, "slug": "new-address", "display_name": ""},
                        {"user_id": third, "slug": "new-address", "bio": "x" * 2001},
                    ):
                        with pytest.raises(IntegrityError):
                            async with connection.begin_nested():
                                await connection.execute(
                                    insert(PublicUserProfile).values(**{**values, **changes})
                                )
                    await connection.execute(delete(User).where(User.id == user))
                    assert (
                        await connection.scalar(
                            select(PublicUserProfile.id).where(PublicUserProfile.id == identity)
                        )
                        is None
                    )
                    assert (
                        await connection.scalar(
                            select(PartnerLanding.description).where(
                                PartnerLanding.id == owned["landing"]
                            )
                        )
                        == "Preserve collection"
                    )
                elif name == "down":
                    assert (
                        await connection.scalar(
                            text("SELECT to_regclass('public.public_user_profiles')")
                        )
                        is None
                    )
                    assert (
                        await connection.scalar(select(User.id).where(User.id == owned["users"][1]))
                        == owned["users"][1]
                    )
                    assert (
                        await connection.scalar(
                            select(PartnerLanding.description).where(
                                PartnerLanding.id == owned["landing"]
                            )
                        )
                        == "Preserve collection"
                    )
                elif name == "cleanup":
                    await connection.execute(
                        delete(PartnerLanding).where(PartnerLanding.id == owned.get("landing"))
                    )
                    await connection.execute(
                        delete(PartnerProfile).where(PartnerProfile.id == owned.get("partner"))
                    )
                    await connection.execute(
                        delete(User).where(User.id.in_(owned.get("users", [])))
                    )
        finally:
            await engine.dispose()

    try:
        asyncio.run(action("seed"))
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("verify"))
        migrate(postgres_url, "downgrade", "20261015_0062")
        asyncio.run(action("down"))
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("cleanup"))


def test_avatar_migration_preserves_profiles_and_sets_null_on_media_deletion(postgres_url):
    """An incorrect downgrade or FK action loses the existing public profile."""
    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20261015_0063")
    owned = {}
    slug = "avatar-migration-" + uuid4().hex

    async def action(name):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                if name == "seed":
                    owned["user"] = await connection.scalar(
                        insert(User).values(internal_identity=uuid4().hex).returning(User.id)
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO public_user_profiles "
                            "(user_id,slug,display_name,bio,is_published,version) "
                            "VALUES (:user,:slug,'Existing name','Keep bio',true,3)"
                        ),
                        {"user": owned["user"], "slug": slug},
                    )
                elif name == "verify":
                    profile = (
                        await connection.execute(
                            select(
                                PublicUserProfile.id,
                                PublicUserProfile.display_name,
                                PublicUserProfile.bio,
                                PublicUserProfile.version,
                                PublicUserProfile.avatar_media_id,
                            ).where(PublicUserProfile.user_id == owned["user"])
                        )
                    ).one()
                    assert tuple(profile)[1:] == ("Existing name", "Keep bio", 3, None)
                    values = dict(
                        bucket_name="migration-private",
                        object_key="profiles/1/" + uuid4().hex + ".webp",
                        content_type="image/webp",
                        size_bytes=1,
                        checksum_sha256="0" * 64,
                        is_public=False,
                    )
                    owned["media"] = await connection.scalar(
                        insert(MediaObject).values(**values).returning(MediaObject.id)
                    )
                    await connection.execute(
                        text("UPDATE public_user_profiles SET avatar_media_id=:media WHERE id=:id"),
                        {"media": owned["media"], "id": profile.id},
                    )
                    await connection.execute(
                        delete(MediaObject).where(MediaObject.id == owned["media"])
                    )
                    assert (
                        await connection.execute(
                            select(PublicUserProfile.id, PublicUserProfile.avatar_media_id).where(
                                PublicUserProfile.id == profile.id
                            )
                        )
                    ).one() == (profile.id, None)
                elif name == "down":
                    assert (
                        await connection.execute(
                            text(
                                "SELECT slug,display_name,bio,is_published,version "
                                "FROM public_user_profiles WHERE user_id=:user"
                            ),
                            {"user": owned["user"]},
                        )
                    ).one() == (slug, "Existing name", "Keep bio", True, 3)
                    assert (
                        await connection.scalar(
                            text(
                                "SELECT count(*) FROM information_schema.columns "
                                "WHERE table_name='public_user_profiles' "
                                "AND column_name='avatar_media_id'"
                            )
                        )
                    ) == 0
                elif name == "cleanup":
                    await connection.execute(delete(User).where(User.id == owned.get("user")))
        finally:
            await engine.dispose()

    try:
        asyncio.run(action("seed"))
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("verify"))
        migrate(postgres_url, "downgrade", "20261015_0063")
        asyncio.run(action("down"))
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("cleanup"))
