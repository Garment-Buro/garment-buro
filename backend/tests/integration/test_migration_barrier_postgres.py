"""Exercise the actual Alembic environment, DDL and interrupted PostgreSQL sessions."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import make_url, pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.migration_lock import acquire_migration_lock

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)
BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def barrier_database(postgres_url):
    source = make_url(postgres_url)
    name = "test_migration_barrier_" + uuid4().hex
    target = source.set(database=name).render_as_string(hide_password=False)

    async def manage(action):
        engine = create_async_engine(source, isolation_level="AUTOCOMMIT", poolclass=pool.NullPool)
        try:
            async with engine.connect() as connection:
                await connection.execute(
                    text(
                        f'{action} DATABASE "{name}"'
                        + (" WITH (FORCE)" if action == "DROP" else "")
                    )
                )
                if action == "CREATE":
                    # Reproduce a server query that outlives a dead client.
                    await connection.execute(
                        text(f'ALTER DATABASE "{name}" SET client_connection_check_interval = 0')
                    )
        finally:
            await engine.dispose()

    asyncio.run(manage("CREATE"))
    try:
        yield target
    finally:
        asyncio.run(manage("DROP"))


def fixture_commands(tmp_path, url):
    versions = tmp_path / "migrations/versions"
    versions.mkdir(parents=True)
    shutil.copyfile(BACKEND / "migrations/env.py", versions.parent / "env.py")
    shutil.copyfile(BACKEND / "alembic.ini", tmp_path / "alembic.ini")
    (versions / "0001.py").write_text("""from alembic import op
revision = "barrier_0001"
down_revision = None
def upgrade():
    op.execute("CREATE TABLE migration_baseline (id integer PRIMARY KEY, payload text NOT NULL)")
    op.execute("INSERT INTO migration_baseline VALUES (1, 'retained')")
def downgrade():
    op.execute("DROP TABLE migration_baseline")
""")
    (versions / "0002.py").write_text("""import os
from alembic import op
revision = "barrier_0002"
down_revision = "barrier_0001"
def upgrade():
    op.execute("CREATE TABLE pending_migration (id integer PRIMARY KEY)")
    op.execute("INSERT INTO pending_migration VALUES (7)")
    op.execute("SELECT pg_advisory_lock(1195537746, 2)")
    if os.environ.get("MIGRATION_TEST_ROLLBACK"):
        raise RuntimeError("Synthetic failure after DDL")
def downgrade():
    op.execute("DROP TABLE pending_migration")
""")
    environment = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "LANG") if k in os.environ}
    environment.update(
        APP_ENV="test", DATABASE_ENABLED="true", DATABASE_URL=url, PYTHONPATH=str(BACKEND)
    )

    def launch(*args, rollback=False):
        return subprocess.Popen(
            [sys.executable, "-m", *args],
            cwd=tmp_path,
            env={**environment, **({"MIGRATION_TEST_ROLLBACK": "1"} if rollback else {})},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    return launch


async def completed(process, timeout=15):
    output, error = await asyncio.to_thread(process.communicate, timeout=timeout)
    return process.returncode, output, error


async def wait_for_lock(connection, key, granted):
    deadline = asyncio.get_running_loop().time() + 15
    while True:
        found = await connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype='advisory' "
                "AND database=(SELECT oid FROM pg_database WHERE datname=current_database()) "
                "AND classid=1195537746 AND objid=:key AND objsubid=2 AND granted=:granted)"
            ),
            {"key": key, "granted": granted},
        )
        if found:
            return
        assert asyncio.get_running_loop().time() < deadline, "Expected PostgreSQL lock was absent"
        await asyncio.sleep(0.05)


@pytest.mark.parametrize("outcome", ["commit", "rollback", "killed-client"])
def test_recovery_waits_for_server_side_ddl_completion(barrier_database, tmp_path, outcome):
    launch = fixture_commands(tmp_path, barrier_database)

    async def scenario():
        setup = launch("alembic", "upgrade", "barrier_0001")
        engine = create_async_engine(barrier_database, poolclass=pool.NullPool)
        migration = waiter = None
        try:
            assert (await completed(setup))[0] == 0
            async with engine.connect() as observer:
                await observer.execute(text("SELECT pg_advisory_lock(1195537746, 2)"))
                try:
                    migration = launch("alembic", "upgrade", "head", rollback=outcome == "rollback")
                    await wait_for_lock(observer, 2, False)
                    await wait_for_lock(observer, 1, True)
                    # A head-only check would still accept the previous version.
                    assert (
                        await observer.scalar(text("SELECT version_num FROM alembic_version"))
                        == "barrier_0001"
                    )
                    waiter = launch("scripts.wait_for_migration")
                    await wait_for_lock(observer, 1, False)
                    assert waiter.poll() is None
                    if outcome == "killed-client":
                        migration.kill()
                        assert (await completed(migration))[0] != 0
                        # Client exit has not ended the PostgreSQL transaction.
                        await wait_for_lock(observer, 2, False)
                        await wait_for_lock(observer, 1, True)
                        assert waiter.poll() is None
                finally:
                    await observer.execute(text("SELECT pg_advisory_unlock(1195537746, 2)"))
                code, output, error = await completed(waiter)
                assert code == 0 and not error
                assert json.loads(output) == {"event": "database.migration_idle"}
                if outcome != "killed-client":
                    code, _, _ = await completed(migration)
                    assert (code == 0) == (outcome == "commit")
                expected = "barrier_0002" if outcome == "commit" else "barrier_0001"
                assert (
                    await observer.scalar(text("SELECT version_num FROM alembic_version"))
                    == expected
                )
                pending = await observer.scalar(
                    text("SELECT to_regclass('public.pending_migration')")
                )
                assert (pending is not None) == (outcome == "commit")
                assert (
                    await observer.scalar(text("SELECT payload FROM migration_baseline WHERE id=1"))
                    == "retained"
                )
                if pending is not None:
                    assert await observer.scalar(text("SELECT id FROM pending_migration")) == 7
        finally:
            for process in (setup, migration, waiter):
                if process is not None and process.poll() is None:
                    process.kill()
                    await completed(process)
            await engine.dispose()

    asyncio.run(scenario())


def test_recovery_timeout_does_not_release_another_migration_lock(barrier_database, tmp_path):
    launch = fixture_commands(tmp_path, barrier_database)

    async def scenario():
        engine = create_async_engine(barrier_database, poolclass=pool.NullPool)
        waiter = None
        try:
            async with engine.connect() as owner:
                await owner.run_sync(acquire_migration_lock)
                waiter = launch("scripts.wait_for_migration")
                await wait_for_lock(owner, 1, False)
                code, output, error = await completed(waiter, timeout=40)
                assert code == 1 and output == ""
                assert json.loads(error)["event"] == "database.migration_wait_failed"
                assert "postgresql://" not in error and "asyncpg://" not in error
                await wait_for_lock(owner, 1, True)
        finally:
            if waiter is not None and waiter.poll() is None:
                waiter.kill()
                await completed(waiter)
            await engine.dispose()

    asyncio.run(scenario())
