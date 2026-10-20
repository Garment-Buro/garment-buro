from __future__ import annotations

import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def backup_environment(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    deployment = tmp_path / "production"
    deployment.mkdir()
    (deployment / ".release").write_text(
        "BACKEND_IMAGE=test-backend\nFRONTEND_IMAGE=test-frontend\n"
    )
    (deployment / ".env").write_text("APP_ENV=production\n")
    (deployment / "docker-compose.yml").write_text("services: {}\n")
    container = tmp_path / "container"
    (container / "tmp").mkdir(parents=True)
    (container / "data").mkdir()
    (container / "data" / "object.txt").write_text("stored media")
    state = tmp_path / "runtime.json"
    state.write_text(
        json.dumps(
            {
                "running": [
                    "postgres",
                    "redis",
                    "minio",
                    "backend",
                    "frontend",
                    "notification-worker",
                    "custom-writer",
                ],
                "calls": [],
                "unstable": {},
            }
        )
    )
    executable = tmp_path / "bin" / "docker"
    executable.parent.mkdir()
    # Emulate Docker transport only. SQLite backup, tar and checksum operations
    # run for real; this does not replace a container deployment rehearsal.
    executable.write_text(
        f"#!{sys.executable}\n"
        + """import json, os, subprocess, sys, tarfile, time
from pathlib import Path
root = Path(os.environ["BACKUP_TEST_CONTAINER"])
state_path = Path(os.environ["BACKUP_TEST_STATE"])
state = json.loads(state_path.read_text())
args = sys.argv[1:]
state["calls"].append(args)
state_path.write_text(json.dumps(state))
failure = os.environ.get("BACKUP_TEST_FAILURE")
def mapped(value):
    return (value.replace("/app/", "__APP__/").replace("/tmp/", "__TMP__/")
            .replace("__APP__", str(root)).replace("__TMP__", str(root / "tmp")))
if args[0] == "info":
    print('["name=rootless"]')
elif args[0] == "inspect":
    print("false 137 false" if failure == "minio-killed" else "false 0 false")
elif args[0] == "run":
    if "--entrypoint" in args and args[args.index("--entrypoint") + 1] == "python":
        if os.environ.get("BACKUP_TEST_BACKEND_FAILURE"):
            sys.exit(42)
        tail = args[args.index("--entrypoint") + 3:]
        sys.exit(subprocess.run([sys.executable, *[mapped(v) for v in tail]]).returncode)
    source = root / ("uploads" if "/app/uploads" in args else "data")
    if failure == "archive":
        sys.exit(45)
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
        archive.add(source, arcname=".")
elif args[0] == "compose":
    args = args[args.index("-f") + 2:]
    if args[:2] == ["--profile", "*"]:
        args = args[2:]
    if args[:2] == ["ps", "-q"]:
        print("test-" + args[-1])
    elif args[0] == "ps":
        status = args[args.index("--status") + 1]
        print("\\n".join(state["running"] if status == "running" else state["unstable"].get(status, [])))
    elif args[0] == "config":
        print("\\n".join(["postgres", "redis", "minio", "backend", "frontend", "notification-worker", "custom-writer", "payment-worker", "migrate"]))
    elif args[0] == "stop":
        targets = [s for s in args[1:] if not s.startswith("-") and s != "60"]
        for service in targets:
            if service in state["running"]: state["running"].remove(service)
            if failure == "stop-writers" and service != "minio":
                state_path.write_text(json.dumps(state)); sys.exit(43)
            if failure == "stop-minio" and service == "minio":
                state_path.write_text(json.dumps(state)); sys.exit(43)
        state_path.write_text(json.dumps(state))
    elif args[0] in {"start", "up"}:
        targets = [s for s in args[1:] if not s.startswith("-") and s not in {"180", "never"}]
        # Real Compose start traverses dependencies and re-executes completed
        # setup jobs; the rootless container rehearsal caught this side effect.
        if any(s in targets for s in ("backend", "frontend")) and "--no-deps" not in args:
            state.setdefault("setup_job_restarts", []).extend(["database-role-init", "minio-init", "migrate"])
        if failure == "resume-minio" and "minio" in targets: sys.exit(46)
        if failure == "resume-apps" and "backend" in targets: sys.exit(47)
        state["running"] = sorted(set(state["running"]) | set(targets))
        state_path.write_text(json.dumps(state))
    elif args[:3] == ["exec", "-T", "postgres"]:
        if "pg_restore" in args:
            assert sys.stdin.buffer.read() == b"postgres-dump"
        else:
            if failure == "dump": sys.exit(44)
            if os.environ.get("BACKUP_TEST_HOLD_DUMP"):
                hold = Path(os.environ["BACKUP_TEST_HOLD_DUMP"])
                hold.with_suffix(".started").touch()
                while hold.exists(): time.sleep(.02)
            sys.stdout.buffer.write(b"postgres-dump")
    else:
        raise AssertionError(args)
else:
    raise AssertionError(args)
"""
    )
    executable.chmod(0o700)
    lock_tool = executable.parent / "flock"
    lock_tool.write_text(
        f"#!{sys.executable}\nimport fcntl, sys\nfcntl.flock(int(sys.argv[-1]), fcntl.LOCK_EX)\n"
    )
    lock_tool.chmod(0o700)
    environment = {
        **{key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG") if key in os.environ},
        "PATH": f"{executable.parent}{os.pathsep}{os.environ['PATH']}",
        "GARMENT_DEPLOY_ROOT": str(tmp_path),
        "BACKUP_TEST_CONTAINER": str(container),
        "BACKUP_TEST_STATE": str(state),
    }
    return tmp_path, environment


def run_backup(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(ROOT / "deploy/scripts/backup-server.sh"), "production"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def check_manifest(backup: Path, expected: set[str]) -> None:
    manifest = {}
    for line in (backup / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        manifest[name] = digest
        assert hashlib.sha256((backup / name).read_bytes()).hexdigest() == digest
    assert manifest.keys() == expected


def test_backup_without_legacy_files_preserves_primary_storage(backup_environment) -> None:
    root, environment = backup_environment
    result = run_backup(environment)
    assert result.returncode == 0, result.stderr
    backup = Path(result.stdout.strip())
    assert backup.is_relative_to(root / "backups/production")
    check_manifest(
        backup,
        {"postgresql.dump", "minio-data.tar.gz", "deployment.env", "release", "docker-compose.yml"},
    )
    assert not (backup / "ecommerce.sqlite3").exists()
    assert not (backup / "legacy-uploads.tar.gz").exists()
    with tarfile.open(backup / "minio-data.tar.gz") as archive:
        assert archive.extractfile("./object.txt").read() == b"stored media"
    assert (backup / "deployment.env").read_text() == "APP_ENV=production\n"
    assert (backup / "release").is_file()
    assert (backup / "docker-compose.yml").is_file()


def test_backup_archives_previous_release_sqlite_and_uploads(backup_environment) -> None:
    _, environment = backup_environment
    container = Path(environment["BACKUP_TEST_CONTAINER"])
    (container / "legacy").mkdir()
    source = container / "legacy/ecommerce.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO orders VALUES (123)")
    (container / "uploads").mkdir()
    (container / "uploads/original.txt").write_text("previous original")
    before = source.read_bytes()
    result = run_backup(environment)
    assert result.returncode == 0, result.stderr
    backup = Path(result.stdout.strip())
    check_manifest(
        backup,
        {
            "postgresql.dump",
            "minio-data.tar.gz",
            "ecommerce.sqlite3",
            "legacy-uploads.tar.gz",
            "deployment.env",
            "release",
            "docker-compose.yml",
        },
    )
    with sqlite3.connect(backup / "ecommerce.sqlite3") as connection:
        assert connection.execute("SELECT id FROM orders").fetchall() == [(123,)]
    assert source.read_bytes() == before
    with tarfile.open(backup / "legacy-uploads.tar.gz") as archive:
        assert archive.extractfile("./original.txt").read() == b"previous original"


@pytest.mark.parametrize("failure", ["transport", "invalid-database"])
def test_backup_does_not_hide_legacy_archive_failures(backup_environment, failure) -> None:
    root, environment = backup_environment
    if failure == "transport":
        environment["BACKUP_TEST_BACKEND_FAILURE"] = "1"
    else:
        container = Path(environment["BACKUP_TEST_CONTAINER"])
        (container / "legacy").mkdir()
        (container / "legacy/ecommerce.db").write_text("broken sqlite")
    result = run_backup(environment)
    assert result.returncode != 0
    assert not list((root / "backups").rglob("SHA256SUMS"))


def test_two_backups_in_the_same_second_cannot_replace_a_completed_bundle(backup_environment):
    root, environment = backup_environment
    clock = root / "bin/date"
    clock.write_text("#!/bin/sh\nprintf '%s\\n' 20261017T120000Z\n")
    clock.chmod(0o700)
    first = run_backup(environment)
    assert first.returncode == 0, first.stderr
    original = Path(first.stdout.strip())
    original_metadata = (original / "deployment.env").read_bytes()
    (root / "production/.env").write_text("APP_ENV=production\nLABEL=second\n")
    second = run_backup(environment)
    assert second.returncode == 0, second.stderr
    assert Path(second.stdout.strip()) != original
    assert (original / "deployment.env").read_bytes() == original_metadata


def test_backup_stops_writers_and_storage_before_reading_and_resumes_exact_services(
    backup_environment,
):
    _, environment = backup_environment
    state_path = Path(environment["BACKUP_TEST_STATE"])
    before = json.loads(state_path.read_text())["running"]
    result = run_backup(environment)
    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text())
    assert set(state["running"]) == set(before)
    assert not state.get("setup_job_restarts")
    calls = state["calls"]
    stops = [i for i, call in enumerate(calls) if "stop" in call]
    dump = next(i for i, call in enumerate(calls) if "postgres" in call and "sh" in call)
    archive = next(i for i, call in enumerate(calls) if call[0] == "run" and "tar" in call)
    starts = [i for i, call in enumerate(calls) if "start" in call or "up" in call]
    assert len(stops) == 2 and len(starts) == 2
    assert stops[0] < stops[1] < dump < archive < starts[0] < starts[1]
    assert "minio" in calls[stops[1]] and "minio" in calls[starts[0]]
    assert {"backend", "frontend", "notification-worker", "custom-writer"} <= set(calls[stops[0]])
    assert not any("payment-worker" in call for call in calls)
    assert not any("exec" in call and "backend" in call for call in calls)
    for index in starts:
        assert {"up", "-d", "--no-deps", "--no-recreate", "--wait"} <= set(calls[index])
        assert calls[index][calls[index].index("--pull") + 1] == "never"
    for call in calls:
        if call[0] == "run":
            assert call[call.index("--network") + 1] == "none"
            assert call[call.index("--volumes-from") + 1].endswith(":ro")


@pytest.mark.parametrize(
    "failure", ["stop-writers", "stop-minio", "dump", "archive", "minio-killed"]
)
def test_backup_failure_resumes_previous_services_and_never_completes_bundle(
    backup_environment, failure
):
    root, environment = backup_environment
    state_path = Path(environment["BACKUP_TEST_STATE"])
    before = json.loads(state_path.read_text())["running"]
    result = run_backup({**environment, "BACKUP_TEST_FAILURE": failure})
    assert result.returncode != 0
    assert not result.stdout.strip()
    assert set(json.loads(state_path.read_text())["running"]) == set(before)
    assert not list((root / "backups").rglob("SHA256SUMS"))


@pytest.mark.parametrize("failure", ["resume-minio", "resume-apps"])
def test_backup_reports_failed_service_recovery_instead_of_success(backup_environment, failure):
    _, environment = backup_environment
    result = run_backup({**environment, "BACKUP_TEST_FAILURE": failure})
    assert result.returncode != 0
    assert not result.stdout.strip()
    assert "manual recovery required" in result.stderr
    calls = json.loads(Path(environment["BACKUP_TEST_STATE"]).read_text())["calls"]
    if failure == "resume-minio":
        assert not any(("start" in call or "up" in call) and "backend" in call for call in calls)


def test_backup_refuses_running_migration_before_stopping_services(backup_environment):
    root, environment = backup_environment
    state_path = Path(environment["BACKUP_TEST_STATE"])
    state = json.loads(state_path.read_text())
    state["running"].append("migrate")
    state_path.write_text(json.dumps(state))
    result = run_backup(environment)
    assert result.returncode == 78
    assert json.loads(state_path.read_text())["running"] == state["running"]
    assert not any("stop" in call for call in json.loads(state_path.read_text())["calls"])
    assert not list((root / "backups").rglob("SHA256SUMS"))


@pytest.mark.parametrize("unstable", ["paused", "restarting", "orphaned"])
def test_backup_refuses_unmanaged_or_unstable_services_before_stopping_anything(
    backup_environment, unstable
):
    _, environment = backup_environment
    state_path = Path(environment["BACKUP_TEST_STATE"])
    state = json.loads(state_path.read_text())
    if unstable == "orphaned":
        state["running"].append("undeclared-writer")
    else:
        state["unstable"] = {unstable: ["backend"]}
    state_path.write_text(json.dumps(state))
    result = run_backup(environment)
    assert result.returncode == 78
    assert not any("stop" in call for call in json.loads(state_path.read_text())["calls"])


def wait_for_file(path: Path) -> None:
    deadline = time.monotonic() + 10
    while not path.exists():
        assert time.monotonic() < deadline, "Backup did not reach controlled dump"
        time.sleep(0.02)


@pytest.mark.parametrize("interruption,code", [(signal.SIGINT, 130), (signal.SIGTERM, 143)])
def test_catchable_interruption_resumes_services_without_completing_backup(
    backup_environment, interruption, code
):
    root, environment = backup_environment
    state_path = Path(environment["BACKUP_TEST_STATE"])
    before = json.loads(state_path.read_text())["running"]
    hold = root / "dump.hold"
    hold.touch()
    process = subprocess.Popen(
        ["bash", str(ROOT / "deploy/scripts/backup-server.sh"), "production"],
        env={**environment, "BACKUP_TEST_HOLD_DUMP": str(hold)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for_file(hold.with_suffix(".started"))
        process.send_signal(interruption)
    finally:
        hold.unlink(missing_ok=True)
        stdout, stderr = process.communicate(timeout=15)
    assert process.returncode == code, stderr
    assert not stdout.strip()
    assert set(json.loads(state_path.read_text())["running"]) == set(before)
    assert not list((root / "backups").rglob("SHA256SUMS"))


def test_manual_backups_serialize_using_the_real_kernel_lock(backup_environment):
    root, environment = backup_environment
    hold = root / "dump.hold"
    hold.touch()
    processes = []
    command = ["bash", str(ROOT / "deploy/scripts/backup-server.sh"), "production"]
    try:
        processes.append(
            subprocess.Popen(
                command,
                env={**environment, "BACKUP_TEST_HOLD_DUMP": str(hold)},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
        wait_for_file(hold.with_suffix(".started"))
        processes.append(
            subprocess.Popen(
                command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
        )
        time.sleep(0.2)
        state = json.loads(Path(environment["BACKUP_TEST_STATE"]).read_text())
        assert len([call for call in state["calls"] if call[0] == "info"]) == 1
        assert processes[1].poll() is None
    finally:
        hold.unlink(missing_ok=True)
        results = [process.communicate(timeout=20) for process in processes]
    assert len(processes) == 2
    for process, (_, stderr) in zip(processes, results, strict=True):
        assert process.returncode == 0, stderr
    assert results[0][0].strip() != results[1][0].strip()


def test_backup_reuses_deployment_lock_inherited_from_its_parent(backup_environment):
    root, environment = backup_environment
    result = subprocess.run(
        [
            "bash",
            "-c",
            'exec 9>"$1/.deploy.lock"; flock -w 1200 9; bash "$2" production',
            "backup-parent",
            str(root),
            str(ROOT / "deploy/scripts/backup-server.sh"),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).is_dir()


def test_backup_does_not_activate_an_api_that_was_already_stopped(backup_environment):
    _, environment = backup_environment
    state_path = Path(environment["BACKUP_TEST_STATE"])
    state = json.loads(state_path.read_text())
    state["running"].remove("backend")
    state_path.write_text(json.dumps(state))
    result = run_backup(environment)
    assert result.returncode == 0, result.stderr
    after = json.loads(state_path.read_text())
    assert set(after["running"]) == set(state["running"])
    assert not any(
        ("start" in call or "up" in call) and "backend" in call for call in after["calls"]
    )


@pytest.mark.parametrize("failure", [None, "dump"])
def test_backup_inside_deployment_resumes_storage_without_starting_writers(
    backup_environment, failure
):
    root, environment = backup_environment
    state_path = Path(environment["BACKUP_TEST_STATE"])
    state = json.loads(state_path.read_text())
    state["running"] = ["postgres", "redis", "minio"]
    state_path.write_text(json.dumps(state))
    result = run_backup({**environment, **({"BACKUP_TEST_FAILURE": failure} if failure else {})})
    after = json.loads(state_path.read_text())
    assert set(after["running"]) == {"postgres", "redis", "minio"}
    starts = [call for call in after["calls"] if "start" in call or "up" in call]
    assert len(starts) == 1 and starts[0][-1] == "minio"
    assert not any("backend" in call or "frontend" in call for call in starts)
    if failure:
        assert result.returncode != 0
        assert not result.stdout.strip()
        assert not list((root / "backups").rglob("SHA256SUMS"))
    else:
        assert result.returncode == 0, result.stderr
        check_manifest(
            Path(result.stdout.strip()),
            {
                "postgresql.dump",
                "minio-data.tar.gz",
                "deployment.env",
                "release",
                "docker-compose.yml",
            },
        )
