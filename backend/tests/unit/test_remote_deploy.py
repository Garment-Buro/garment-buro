"""Exercise the release script; emulate Docker, public probes and Linux host tools.

This verifies command ordering and recovery, not a real container release.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
REVISION = "a" * 40


@pytest.fixture
def release_environment(tmp_path):
    deployment = tmp_path / "production"
    deployment.mkdir()
    (deployment / ".env").write_text(
        "APP_ENV=production\nIDENTITY_API_ENABLED=true\n"
        "FRONTEND_HOST_PORT=3100\nBACKEND_HOST_PORT=8108\nHOST_BIND_ADDRESS=127.0.0.1\n"
    )
    (deployment / ".env").chmod(0o600)
    (deployment / ".release").write_text(
        "BACKEND_IMAGE=previous-backend\nFRONTEND_IMAGE=previous-frontend\n"
    )
    old_services = [
        "backend",
        "frontend",
        "notification-worker",
        "database-role-init",
        "migrate",
        "minio-init",
    ]
    new_services = [
        *old_services,
        "project-media-worker",
        "database-role-init",
        "migrate",
        "minio-init",
    ]
    for name, services in [
        ("docker-compose.yml", old_services),
        ("docker-compose.next.yml", new_services),
    ]:
        definitions = {service: {} for service in services}
        definitions["backend"]["depends_on"] = {"migrate": {}, "minio-init": {}}
        definitions["migrate"]["depends_on"] = {"database-role-init": {}}
        definitions["notification-worker"]["depends_on"] = {"backend": {}}
        (deployment / name).write_text(json.dumps({"services": definitions}))
    backup_builder = tmp_path / "build-fixture-backup.py"
    backup_builder.write_text("""import hashlib, json, os, shutil, tarfile, time
from pathlib import Path
root = Path(os.environ["GARMENT_DEPLOY_ROOT"])
state_path = Path(os.environ["DEPLOY_TEST_STATE"])
state = json.loads(state_path.read_text())
state["running_at_backup"] = dict(state["running"])
state["calls"].append(["backup"])
state_path.write_text(json.dumps(state))
if os.environ.get("DEPLOY_TEST_HOLD_BACKUP"):
    hold = Path(os.environ["DEPLOY_TEST_HOLD_BACKUP"])
    hold.with_suffix(".started").touch()
    while hold.exists(): time.sleep(.02)
target = root / "backups/production/fixture-bundle"
target.mkdir(parents=True, mode=0o700)
(target / "postgresql.dump").write_bytes(b"PGDMP transport fixture")
with tarfile.open(target / "minio-data.tar.gz", "w:gz"):
    pass
for source, destination in [(".env", "deployment.env"), (".release", "release"), ("docker-compose.yml", "docker-compose.yml")]:
    shutil.copyfile(root / "production" / source, target / destination)
entries = list(target.iterdir())
(target / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\\n" for p in entries))
for p in target.iterdir(): p.chmod(0o600)
if os.environ.get("DEPLOY_TEST_FAILURE") == "backup":
    (target / "release").write_text("corrupted after hashing")
if os.environ.get("DEPLOY_TEST_FAILURE") == "backup-writer-resumed":
    state["running"]["backend"] = "previous-backend"
    state_path.write_text(json.dumps(state))
print(target)
""")
    (deployment / "backup-server.next.sh").write_text(
        f"#!/usr/bin/env bash\n{shlex.quote(sys.executable)} {shlex.quote(str(backup_builder))}\n"
    )
    shutil.copyfile(ROOT / "deploy/scripts/verify-backup.py", deployment / "verify-backup.next.py")
    (deployment / "public-maintenance.next.py").write_text(
        "import importlib.util, json, os\nfrom pathlib import Path\n"
        f"spec=importlib.util.spec_from_file_location('gate', {str(ROOT / 'deploy/scripts/public-maintenance.py')!r})\n"
        "gate=importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)\n"
        "def verify(origins, environment, closed):\n"
        " p=Path(os.environ['DEPLOY_TEST_STATE']); state=json.loads(p.read_text())\n"
        " state['calls'].append(['public-gate', 'closed' if closed else 'open'])\n"
        " state.setdefault('public_probes', []).append({'closed':closed,'running':dict(state['running']),'release':(Path(os.environ['GARMENT_DEPLOY_ROOT'])/'production/.release').read_text()})\n"
        " p.write_text(json.dumps(state))\n"
        " failure=os.environ.get('DEPLOY_TEST_GATE_FAILURE')\n"
        " if failure=='check' or failure=='close' and closed or failure=='open' and not closed and len(state['public_probes'])>1:\n"
        "  raise gate.GateError('Public gate fixture failure')\n"
        "gate.verify=verify\nraise SystemExit(gate.main())\n"
    )
    state_path = tmp_path / "runtime.json"
    state_path.write_text(
        json.dumps(
            {
                "running": {
                    "backend": "previous-backend",
                    "frontend": "previous-frontend",
                    "notification-worker": "previous-backend",
                },
                "projects_bucket": False,
                "calls": [],
            }
        )
    )
    executable = tmp_path / "bin" / "host-tool"
    executable.parent.mkdir()
    executable.write_text(
        f"#!{sys.executable}\n"
        + """import json, os, subprocess, sys, time
from pathlib import Path
state_path = Path(os.environ["DEPLOY_TEST_STATE"])
state = json.loads(state_path.read_text())
state.setdefault("containers", dict(state["running"]))
tool, args = Path(sys.argv[0]).name, sys.argv[1:]
state["calls"].append([tool, *args])
code = 0
if tool == "stat":
    print(oct(Path(args[-1]).stat().st_mode & 0o777)[2:])
elif tool == "flock":
    pass
elif tool == "timeout":
    sys.exit(subprocess.run(args[1:], timeout=int(args[0])).returncode)
elif tool == "install":
    if os.environ.get("DEPLOY_TEST_FAILURE") == "metadata" and args[-1] == "backup-server.sh":
        code = 49
    else:
        code = subprocess.run([os.environ["DEPLOY_TEST_INSTALL"], *args]).returncode
elif tool == "curl":
    state.setdefault("workers_at_http", []).append(sorted(name for name in state["running"] if name.endswith("-worker") or name == "payment-reconciler"))
    state.setdefault("applications_at_http", []).append({name: image for name, image in state["running"].items() if name in {"backend", "frontend"}})
    candidate = any(image != "previous-backend" for name,image in state["running"].items() if name == "backend")
    code = 22 if candidate and os.environ.get("DEPLOY_TEST_FAILURE") in {"http", "resume", "stop-apps"} or not candidate and os.environ.get("DEPLOY_TEST_RECOVERY_HTTP_FAIL") else 0
elif tool == "docker":
    if args[0] == "info":
        print('["name=rootless"]')
    elif args[0] == "pull":
        pass
    elif args[:2] == ["image", "inspect"]:
        code = 1 if os.environ.get("DEPLOY_TEST_STORAGE_MISSING") else 0
        if not code: print("sha256:" + "1" * 64)
    elif args[0] == "ps":
        if os.environ.get("DEPLOY_TEST_MIGRATION_LEFTOVER"):
            print("garment-buro-production-migrate-" + "a" * 40)
        if os.environ.get("DEPLOY_TEST_MIGRATION_INSPECT_FAIL"):
            code = 52
    elif args[:2] == ["rm", "--force"]:
        if os.environ.get("DEPLOY_TEST_MIGRATION_REMOVE_FAIL"):
            code = 53
    elif args[0] == "compose":
        descriptor = Path(args[args.index("-f") + 1])
        services = json.loads(descriptor.read_text())["services"]
        if "config" in args:
            if "--services" in args:
                print("\\n".join(services))
            elif "--images" in args:
                print(os.environ.get("DEPLOY_TEST_STORAGE_IMAGE", "garment-buro-minio:2025-10-15-garment1"))
        elif "ps" in args:
            status = args[args.index("--status")+1] if "--status" in args else "running"
            print("\\n".join(state.get(status, {}) if status != "running" else state["running"]))
        elif "run" in args:
            service = args[-1]
            if "scripts.wait_for_migration" in args:
                state["running_at_migration_barrier"] = dict(state["running"])
                state["migration_barrier_image"] = os.environ["BACKEND_IMAGE"]
                if os.environ.get("DEPLOY_TEST_MIGRATION_BARRIER_FAIL"):
                    code = 54
            if "--check-heads" in args:
                state["running_at_schema_check"] = dict(state["running"])
                state["schema_check_image"] = os.environ["BACKEND_IMAGE"]
                if os.environ.get("DEPLOY_TEST_SCHEMA_CHECK") in {"mismatch", "unavailable"}:
                    code = 51
            if service == "migrate":
                state["workers_at_migration"] = sorted(name for name in state["running"] if name.endswith("-worker") or name == "payment-reconciler")
                state["applications_at_migration"] = {name: image for name, image in state["running"].items() if name in {"backend", "frontend"}}
                if os.environ.get("DEPLOY_TEST_HOLD_MIGRATION"):
                    state_path.write_text(json.dumps(state))
                    hold = Path(os.environ["DEPLOY_TEST_HOLD_MIGRATION"])
                    hold.with_suffix(".started").touch()
                    while hold.exists(): time.sleep(.02)
                if os.environ.get("DEPLOY_TEST_FAILURE") in {"migrate", "resume-apps"}:
                    code = 46
            if service == "minio-init":
                if os.environ.get("DEPLOY_TEST_FAILURE") == "init":
                    code = 41
                else:
                    state["projects_bucket"] = True
        elif "stop" in args:
            targets = [name for name in args[args.index("stop") + 1:] if name in services]
            failure = os.environ.get("DEPLOY_TEST_FAILURE")
            candidate = descriptor.name.endswith("next.yml")
            applications = any(name in {"backend", "frontend"} for name in targets)
            if (failure == "stop" and candidate) or (failure == "pause" and not candidate) or (failure == "pause-apps" and not candidate and applications) or (failure == "stop-apps" and candidate and applications):
                code = 43
                if failure in {"pause", "pause-apps"} and targets:
                    state["running"].pop(targets[0], None)
            elif failure == "pause-noop" and not candidate and applications:
                pass
            else:
                for name in targets:
                    state["running"].pop(name, None)
        elif "up" in args:
            tail = args[args.index("up") + 1:]
            targets = [name for name in tail if not name.startswith("-") and name not in {"never", "180", "60"}]
            if any(name not in services for name in targets):
                print("no such service", file=sys.stderr)
                code = 44
            else:
                for name in targets:
                    state["running"][name] = (state["containers"][name] if "--no-recreate" in args else os.environ["FRONTEND_IMAGE" if name == "frontend" else "BACKEND_IMAGE"])
                    state["containers"][name] = state["running"][name]
                failure = os.environ.get("DEPLOY_TEST_FAILURE")
                if "--no-recreate" in args and (failure == "resume" and "notification-worker" in targets or failure == "resume-apps" and "backend" in targets):
                    for name in targets:
                        state["running"].pop(name, None)
                    code = 48
                if descriptor.name.endswith("next.yml"):
                    failure = os.environ.get("DEPLOY_TEST_FAILURE")
                    if (failure == "health" and "backend" in targets) or (failure in {"stop", "workers", "restore-worker"} and any(name.endswith("-worker") for name in targets)):
                        code = 42
                elif os.environ.get("DEPLOY_TEST_FAILURE") == "restore-worker" and "notification-worker" in targets:
                    state["running"].pop("notification-worker", None)
                    code = 47
        elif "start" in args:
            targets = [name for name in args[args.index("start") + 1:] if name in services]
            failure = os.environ.get("DEPLOY_TEST_FAILURE")
            if failure == "resume" or (failure == "resume-apps" and "backend" in targets):
                code = 48
            else:
                for name in targets:
                    state["running"][name] = state["containers"][name]
        else:
            raise AssertionError(args)
        if ("start" in args or "up" in args) and "--no-deps" not in args:
            pending = list(targets)
            visited = set()
            while pending:
                name = pending.pop()
                if name in visited:
                    continue
                visited.add(name)
                pending.extend(services[name].get("depends_on", {}))
            state.setdefault("setup_job_restarts", []).extend(sorted(visited & {"database-role-init", "migrate", "minio-init"}))
    else:
        raise AssertionError(args)
else:
    raise AssertionError(tool)
state.setdefault("maintenance_observations", []).append({"tool":tool,"args":args,"closed":(Path(os.environ["GARMENT_DEPLOY_ROOT"])/"maintenance/production.active").is_file()})
state_path.write_text(json.dumps(state))
sys.exit(code)
"""
    )
    executable.chmod(0o700)
    for name in ["docker", "curl", "stat", "flock", "timeout", "install"]:
        (executable.parent / name).symlink_to(executable)
    environment = {
        **{key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG") if key in os.environ},
        "PATH": f"{executable.parent}{os.pathsep}{os.environ['PATH']}",
        "GARMENT_DEPLOY_ROOT": str(tmp_path),
        "DEPLOY_TEST_STATE": str(state_path),
        "DEPLOY_TEST_INSTALL": shutil.which("install"),
    }
    return deployment, state_path, environment


def run_release(environment):
    return subprocess.run(
        [
            "bash",
            str(ROOT / "deploy/scripts/remote-deploy.sh"),
            "production",
            f"ghcr.io/garment-buro/garment-buro-backend:production-{REVISION}",
            f"ghcr.io/garment-buro/garment-buro-frontend:production-{REVISION}",
            REVISION,
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_release_initializes_new_bucket_before_application_cutover(release_environment):
    deployment, state_path, environment = release_environment
    result = run_release(environment)
    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text())
    assert state["projects_bucket"]
    assert "project-media-worker" in state["running"]
    calls = state["calls"]
    init = next(i for i, call in enumerate(calls) if "run" in call and call[-1] == "minio-init")
    cutover = next(i for i, call in enumerate(calls) if "up" in call)
    assert init < cutover
    assert REVISION in (deployment / ".release").read_text()
    assert (deployment / "verify-backup.py").read_bytes() == (
        ROOT / "deploy/scripts/verify-backup.py"
    ).read_bytes()
    pointers = list(deployment.parent.glob("backups/production/*/storage-backup.path"))
    assert len(pointers) == 1
    assert (Path(pointers[0].read_text().strip()) / "SHA256SUMS").is_file()


def test_public_gate_remains_closed_until_workers_and_release_metadata_are_ready(
    release_environment,
):
    deployment, state_path, environment = release_environment
    result = run_release(environment)
    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text())
    assert [probe["closed"] for probe in state["public_probes"]] == [False, True, False]
    final = state["public_probes"][-1]
    assert REVISION in final["release"]
    assert {"backend", "frontend", "notification-worker", "project-media-worker"} <= final[
        "running"
    ].keys()
    changes = [
        entry
        for entry in state["maintenance_observations"]
        if entry["tool"] == "curl"
        or entry["tool"] == "docker"
        and any(command in entry["args"] for command in ["stop", "up", "run"])
    ]
    assert changes and all(entry["closed"] for entry in changes)
    assert not (deployment.parent / "maintenance/production.active").exists()


@pytest.mark.parametrize("failure", ["check", "close"])
def test_unconfirmed_public_gate_never_pauses_the_old_application(release_environment, failure):
    deployment, state_path, environment = release_environment
    original = json.loads(state_path.read_text())["running"]
    metadata = (deployment / ".release").read_bytes()
    result = run_release({**environment, "DEPLOY_TEST_GATE_FAILURE": failure})
    assert result.returncode == 78, result.stderr
    state = json.loads(state_path.read_text())
    assert state["running"] == original
    assert (deployment / ".release").read_bytes() == metadata
    assert not any(
        call == ["backup"] or "stop" in call or "up" in call or "run" in call
        for call in state["calls"]
    )


def test_foreign_maintenance_and_missing_controller_stop_before_application_changes(
    release_environment,
):
    deployment, state_path, environment = release_environment
    marker = deployment.parent / "maintenance/production.active"
    marker.parent.mkdir()
    marker.write_text("an earlier interrupted release")
    result = run_release(environment)
    assert result.returncode == 78
    assert marker.read_text() == "an earlier interrupted release"
    assert not any(
        "pull" in call or "stop" in call for call in json.loads(state_path.read_text())["calls"]
    )
    (deployment / "public-maintenance.next.py").unlink()
    assert run_release(environment).returncode == 78


def test_schema_rejection_keeps_public_maintenance_active(release_environment):
    deployment, state_path, environment = release_environment
    result = run_release(
        {**environment, "DEPLOY_TEST_FAILURE": "health", "DEPLOY_TEST_SCHEMA_CHECK": "mismatch"}
    )
    assert result.returncode == 42, result.stderr
    assert (deployment.parent / "maintenance/production.active").is_file()
    state = json.loads(state_path.read_text())
    assert not state["running"]
    assert [probe["closed"] for probe in state["public_probes"]] == [False, True]


def test_recovery_http_failure_does_not_reopen_public_traffic(release_environment):
    deployment, state_path, environment = release_environment
    result = run_release(
        {**environment, "DEPLOY_TEST_FAILURE": "init", "DEPLOY_TEST_RECOVERY_HTTP_FAIL": "1"}
    )
    assert result.returncode == 41, result.stderr
    assert "HTTP probe failed" in result.stderr
    assert (deployment.parent / "maintenance/production.active").is_file()
    assert len(json.loads(state_path.read_text())["public_probes"]) == 2


def test_partial_public_reopening_keeps_committed_candidate_and_recloses_gate(release_environment):
    deployment, state_path, environment = release_environment
    result = run_release({**environment, "DEPLOY_TEST_GATE_FAILURE": "open"})
    assert result.returncode == 78, result.stderr
    assert "keep candidate images" in result.stderr
    assert (deployment.parent / "maintenance/production.active").is_file()
    assert REVISION in (deployment / ".release").read_text()
    state = json.loads(state_path.read_text())
    assert all(REVISION in image for image in state["running"].values())
    assert not any("--check-heads" in call for call in state["calls"])
    assert not any("stop" in call and "docker-compose.next.yml" in call for call in state["calls"])


@pytest.mark.parametrize(
    "failure",
    [
        {"DEPLOY_TEST_STORAGE_MISSING": "1"},
        {"DEPLOY_TEST_STORAGE_IMAGE": "unexpected:one\nunexpected:two"},
    ],
)
def test_release_requires_prepared_storage_before_backup_or_stopping_writers(
    release_environment, failure
):
    deployment, state_path, environment = release_environment
    before = json.loads(state_path.read_text())["running"]
    metadata = (deployment / ".release").read_bytes()
    result = run_release({**environment, **failure})
    assert result.returncode == 78, result.stderr
    state = json.loads(state_path.read_text())
    assert state["running"] == before
    assert (deployment / ".release").read_bytes() == metadata
    assert not list(deployment.parent.glob("backups/production/*"))
    assert not any(call[:2] == ["docker", "pull"] or call == ["backup"] for call in state["calls"])
    assert not any(
        call[:2] == ["docker", "compose"] and any(step in call for step in ["stop", "up", "run"])
        for call in state["calls"]
    )


def test_rollback_stops_new_worker_and_restores_only_previous_services(release_environment):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_text()
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": "health"})
    assert result.returncode == 42, result.stderr
    state = json.loads(state_path.read_text())
    assert state["running"] == {
        "backend": "previous-backend",
        "frontend": "previous-frontend",
        "notification-worker": "previous-backend",
    }
    assert (deployment / ".release").read_text() == before


def test_storage_init_failure_keeps_previous_release_running(release_environment):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_text()
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": "init"})
    assert result.returncode == 41, result.stderr
    state = json.loads(state_path.read_text())
    assert state["running"]["backend"] == "previous-backend"
    assert not state.get("setup_job_restarts"), "Recovery reran completed deployment setup jobs"
    resumes = [call for call in state["calls"] if "up" in call]
    assert resumes
    assert all(
        all(option in call for option in ["--no-deps", "--no-recreate", "--wait"])
        and call[call.index("--pull") + 1] == "never"
        for call in resumes
    )
    assert (deployment / ".release").read_text() == before


def test_rollback_stop_failure_is_reported_and_does_not_start_old_api(release_environment):
    _, state_path, environment = release_environment
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": "stop"})
    assert result.returncode != 0
    assert "Rollback failed" in result.stderr
    state = json.loads(state_path.read_text())
    assert state["running"]["backend"] != "previous-backend"


def test_missing_backup_verifier_stops_release_before_application_changes(release_environment):
    deployment, state_path, environment = release_environment
    (deployment / "verify-backup.next.py").unlink()
    before = (deployment / ".release").read_bytes()
    result = run_release(environment)
    assert result.returncode == 78
    state = json.loads(state_path.read_text())
    assert not any("up" in call or "pull" in call for call in state["calls"])
    assert (deployment / ".release").read_bytes() == before


def test_corrupt_backup_stops_release_before_migration_or_application_cutover(release_environment):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_bytes()
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": "backup"})
    assert result.returncode == 1
    state = json.loads(state_path.read_text())
    assert not any(
        "migrate" in call or "up" in call and "docker-compose.next.yml" in call
        for call in state["calls"]
    )
    assert state["running_at_backup"] == {}
    assert state["running"] == {
        "backend": "previous-backend",
        "frontend": "previous-frontend",
        "notification-worker": "previous-backend",
    }
    assert (deployment / ".release").read_bytes() == before


def test_release_keeps_writers_stopped_from_backup_until_candidate(release_environment):
    _, state_path, environment = release_environment
    result = run_release(environment)
    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text())
    assert state["running_at_backup"] == {}
    calls = state["calls"]
    backup = calls.index(["backup"])
    migration = next(i for i, call in enumerate(calls) if "run" in call and call[-1] == "migrate")
    cutover = next(i for i, call in enumerate(calls) if "up" in call and "backend" in call)
    assert backup < migration < cutover
    assert not any("start" in call or "up" in call for call in calls[backup:cutover])


def test_release_rechecks_writers_after_backup_before_migration(release_environment):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_bytes()
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": "backup-writer-resumed"})
    assert result.returncode == 78, result.stderr
    state = json.loads(state_path.read_text())
    assert not any("run" in call and call[-1] == "migrate" for call in state["calls"])
    assert state["running"] == {
        "backend": "previous-backend",
        "frontend": "previous-frontend",
        "notification-worker": "previous-backend",
    }
    assert (deployment / ".release").read_bytes() == before


ALL_WORKERS = [
    "notification-worker",
    "project-media-worker",
    "payment-worker",
    "payment-reconciler",
    "fulfillment-worker",
    "cdek-worker",
    "order-workflow-worker",
]


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({}, set()),
        (
            {"PAYMENT_WEBHOOK_V2_ENABLED": "true", "CDEK_CREATION_ENABLED": "true"},
            {"payment-worker", "cdek-worker"},
        ),
        (
            {
                "IDENTITY_API_ENABLED": "true",
                "PAYMENT_CREATION_ENABLED": "true",
                "PAYMENT_MANAGEMENT_ENABLED": "true",
            },
            {"notification-worker", "project-media-worker", "order-workflow-worker"},
        ),
    ],
    ids=["all-disabled", "selected-providers", "identity-and-workflows"],
)
def test_release_replaces_running_worker_set_after_http_checks(
    release_environment, flags, expected
):
    deployment, state_path, environment = release_environment
    settings = (deployment / ".env").read_text().replace("IDENTITY_API_ENABLED=true\n", "")
    (deployment / ".env").write_text(
        settings + "".join(f"{key}={value}\n" for key, value in flags.items())
    )
    for name in ("docker-compose.yml", "docker-compose.next.yml"):
        path = deployment / name
        descriptor = json.loads(path.read_text())
        descriptor["services"].update({worker: {} for worker in ALL_WORKERS})
        path.write_text(json.dumps(descriptor))
    state = json.loads(state_path.read_text())
    state["running"].update({worker: "previous-backend" for worker in ALL_WORKERS})
    state_path.write_text(json.dumps(state))
    result = run_release(environment)
    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text())
    assert {worker for worker in ALL_WORKERS if worker in state["running"]} == expected
    assert state["workers_at_migration"] == []
    assert len(state["workers_at_http"]) == 5
    assert all(not workers for workers in state["workers_at_http"])
    assert all(REVISION in state["running"][worker] for worker in expected)


@pytest.mark.parametrize("failure", ["http", "migrate", "pause", "workers", "metadata"])
def test_failed_worker_cutover_restores_previous_running_set(release_environment, failure):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_bytes()
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": failure})
    assert result.returncode != 0
    state = json.loads(state_path.read_text())
    assert state["running"] == {
        "backend": "previous-backend",
        "frontend": "previous-frontend",
        "notification-worker": "previous-backend",
    }
    assert (deployment / ".release").read_bytes() == before
    if failure in {"pause", "migrate"}:
        assert not any(
            "up" in call and "backend" in call and "docker-compose.next.yml" in call
            for call in state["calls"]
        )
    if failure == "http":
        assert not any("up" in call and "project-media-worker" in call for call in state["calls"])
    if failure in {"http", "migrate", "pause"}:
        assert any(
            "up" in call and "notification-worker" in call and "--no-recreate" in call
            for call in state["calls"]
        )
        assert not any(
            "up" in call and "notification-worker" in call and "docker-compose.next.yml" in call
            for call in state["calls"]
        )


@pytest.mark.parametrize("failure", [None, "health", "workers"])
def test_worker_cutover_never_activates_dormant_previous_service(release_environment, failure):
    _, state_path, environment = release_environment
    state = json.loads(state_path.read_text())
    state["running"].pop("notification-worker")
    state_path.write_text(json.dumps(state))
    result = run_release({**environment, **({"DEPLOY_TEST_FAILURE": failure} if failure else {})})
    state = json.loads(state_path.read_text())
    if failure:
        assert result.returncode != 0
        assert set(state["running"]) == {"backend", "frontend"}
    else:
        assert result.returncode == 0, result.stderr
        assert {"notification-worker", "project-media-worker"} <= state["running"].keys()


@pytest.mark.parametrize("failure", ["restore-worker", "resume"])
def test_worker_restore_failure_is_explicit_and_does_not_publish_release(
    release_environment, failure
):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_bytes()
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": failure})
    assert result.returncode != 0
    assert "Rollback failed to restore previous workers" in result.stderr
    state = json.loads(state_path.read_text())
    assert state["running"] == {"backend": "previous-backend", "frontend": "previous-frontend"}
    assert (deployment / ".release").read_bytes() == before


@pytest.mark.parametrize(("interrupt", "expected"), [(signal.SIGINT, 130), (signal.SIGTERM, 143)])
@pytest.mark.parametrize("phase", ["migration", "backup"])
def test_interrupted_release_resumes_paused_writers(
    release_environment, interrupt, expected, phase
):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_bytes()
    hold = deployment.parent / f"{phase}.hold"
    hold.touch()
    process = subprocess.Popen(
        [
            "bash",
            str(ROOT / "deploy/scripts/remote-deploy.sh"),
            "production",
            f"ghcr.io/garment-buro/garment-buro-backend:production-{REVISION}",
            f"ghcr.io/garment-buro/garment-buro-frontend:production-{REVISION}",
            REVISION,
        ],
        env={**environment, f"DEPLOY_TEST_HOLD_{phase.upper()}": str(hold)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not hold.with_suffix(".started").exists():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.02)
        assert "notification-worker" not in json.loads(state_path.read_text())["running"]
        state = json.loads(state_path.read_text())
        assert not {"backend", "frontend"}.intersection(state["running"])
        assert state["running_at_backup"] == {}
        if phase == "migration":
            assert state["applications_at_migration"] == {}
        process.send_signal(interrupt)
        hold.unlink()
        _, error = process.communicate(timeout=15)
        assert process.returncode == expected, error
        assert json.loads(state_path.read_text())["running"] == {
            "backend": "previous-backend",
            "frontend": "previous-frontend",
            "notification-worker": "previous-backend",
        }
        assert (deployment / ".release").read_bytes() == before
    finally:
        hold.unlink(missing_ok=True)
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=15)


def test_migrations_run_without_old_applications_and_http_uses_only_candidate(release_environment):
    _, state_path, environment = release_environment
    result = run_release(environment)
    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text())
    assert state["applications_at_migration"] == {}
    assert state["workers_at_migration"] == []
    assert len(state["applications_at_http"]) == 5
    assert all(
        set(apps) == {"backend", "frontend"} and all(REVISION in image for image in apps.values())
        for apps in state["applications_at_http"]
    )
    calls = state["calls"]
    worker_stop = next(
        i for i, call in enumerate(calls) if "stop" in call and "notification-worker" in call
    )
    app_stop = next(i for i, call in enumerate(calls) if "stop" in call and "backend" in call)
    migration = next(i for i, call in enumerate(calls) if "run" in call and call[-1] == "migrate")
    assert worker_stop < app_stop < migration


@pytest.mark.parametrize("failure", ["pause-apps", "migrate", "pause-noop"])
def test_before_candidate_failure_resumes_existing_app_containers(release_environment, failure):
    deployment, state_path, environment = release_environment
    # A moved tag or changed descriptor must not replace paused containers.
    before = b"BACKEND_IMAGE=moved-backend-tag\nFRONTEND_IMAGE=moved-frontend-tag\n"
    (deployment / ".release").write_bytes(before)
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": failure})
    assert result.returncode != 0
    state = json.loads(state_path.read_text())
    assert state["running"] == {
        "backend": "previous-backend",
        "frontend": "previous-frontend",
        "notification-worker": "previous-backend",
    }
    calls = state["calls"]
    assert any("up" in call and "backend" in call and "--no-recreate" in call for call in calls)
    assert not any("up" in call and "docker-compose.next.yml" in call for call in calls)
    assert not state.get("setup_job_restarts")
    if failure != "migrate":
        assert not any("run" in call and call[-1] == "migrate" for call in calls)
    assert (deployment / ".release").read_bytes() == before


@pytest.mark.parametrize("dormant", ["backend", "frontend", "both"])
@pytest.mark.parametrize("failure", ["init", "http"])
def test_failed_candidate_does_not_activate_previously_stopped_application(
    release_environment, dormant, failure
):
    _, state_path, environment = release_environment
    state = json.loads(state_path.read_text())
    dormant_services = ["backend", "frontend"] if dormant == "both" else [dormant]
    for service in dormant_services:
        state["running"].pop(service)
    state_path.write_text(json.dumps(state))
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": failure})
    assert result.returncode != 0
    state = json.loads(state_path.read_text())
    assert all(service not in state["running"] for service in dormant_services)
    assert all(image.startswith("previous-") for image in state["running"].values())


def test_failed_application_resume_does_not_resume_workers(release_environment):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_bytes()
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": "resume-apps"})
    assert result.returncode != 0
    assert "Rollback failed to restore previous applications" in result.stderr
    state = json.loads(state_path.read_text())
    assert not any(
        ("start" in call or "up" in call) and "notification-worker" in call
        for call in state["calls"]
    )
    assert (deployment / ".release").read_bytes() == before


def test_failed_candidate_app_stop_does_not_restart_previous_apps_or_workers(release_environment):
    _, state_path, environment = release_environment
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": "stop-apps"})
    assert result.returncode != 0
    assert "Rollback failed to stop candidate applications" in result.stderr
    state = json.loads(state_path.read_text())
    assert not any(
        ("up" in call or "start" in call) and "docker-compose.yml" in call
        for call in state["calls"]
    )


@pytest.mark.parametrize("service", ["custom-writer", "orphan-worker", "migrate"])
def test_release_refuses_unmanaged_running_writer_or_active_setup_job(release_environment, service):
    deployment, state_path, environment = release_environment
    if service != "orphan-worker":
        path = deployment / "docker-compose.yml"
        descriptor = json.loads(path.read_text())
        descriptor["services"][service] = {}
        path.write_text(json.dumps(descriptor))
    state = json.loads(state_path.read_text())
    state["running"][service] = "previous-backend"
    state_path.write_text(json.dumps(state))
    result = run_release(environment)
    assert result.returncode == 78, result.stderr
    state = json.loads(state_path.read_text())
    assert not any("stop" in call or "up" in call or "start" in call for call in state["calls"])


@pytest.mark.parametrize("status", ["paused", "restarting"])
def test_release_refuses_unstable_previous_services(release_environment, status):
    _, state_path, environment = release_environment
    state = json.loads(state_path.read_text())
    state[status] = {"backend": "previous-backend"}
    state_path.write_text(json.dumps(state))
    result = run_release(environment)
    assert result.returncode == 78, result.stderr
    state = json.loads(state_path.read_text())
    assert not any("stop" in call or "up" in call or "start" in call for call in state["calls"])


def test_application_cutover_keeps_existing_infrastructure_running(release_environment):
    deployment, state_path, environment = release_environment
    infrastructure = {service: "unchanged-" + service for service in ["postgres", "redis", "minio"]}
    for name in ["docker-compose.yml", "docker-compose.next.yml"]:
        path = deployment / name
        descriptor = json.loads(path.read_text())
        descriptor["services"].update({service: {} for service in infrastructure})
        path.write_text(json.dumps(descriptor))
    state = json.loads(state_path.read_text())
    state["running"].update(infrastructure)
    state_path.write_text(json.dumps(state))
    result = run_release(environment)
    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text())
    assert {name: state["running"][name] for name in infrastructure} == infrastructure
    assert state["applications_at_migration"] == {}
    for call in state["calls"]:
        if any(action in call for action in ["stop", "up", "start"]):
            assert not set(call).intersection(infrastructure)


@pytest.mark.parametrize("failure", ["migrate", "http", "workers", "metadata"])
@pytest.mark.parametrize("schema_check", ["mismatch", "unavailable"])
def test_recovery_does_not_resume_old_writers_without_schema_acceptance(
    release_environment, failure, schema_check
):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_bytes()
    result = run_release(
        {
            **environment,
            "DEPLOY_TEST_FAILURE": failure,
            "DEPLOY_TEST_SCHEMA_CHECK": schema_check,
        }
    )
    assert result.returncode != 0
    assert "Previous backend did not accept the database schema" in result.stderr
    assert "manual recovery required" in result.stderr
    state = json.loads(state_path.read_text())
    assert state["running_at_schema_check"] == {}
    assert state["schema_check_image"] == "previous-backend"
    assert state["running"] == {}
    calls = state["calls"]
    check = next(i for i, call in enumerate(calls) if "--check-heads" in call)
    assert not any("start" in call or "up" in call for call in calls[check + 1 :])
    assert (deployment / ".release").read_bytes() == before
    pointers = list(deployment.parent.glob("backups/production/*/storage-backup.path"))
    assert len(pointers) == 1
    assert (Path(pointers[0].read_text().strip()) / "SHA256SUMS").is_file()


@pytest.mark.parametrize("failure", ["migrate", "http", "workers"])
def test_recovery_checks_old_image_before_starting_previous_writers(release_environment, failure):
    _, state_path, environment = release_environment
    result = run_release({**environment, "DEPLOY_TEST_FAILURE": failure})
    assert result.returncode != 0
    state = json.loads(state_path.read_text())
    assert state["schema_check_image"] == "previous-backend"
    assert state["running_at_schema_check"] == {}
    calls = state["calls"]
    migration = next(i for i, call in enumerate(calls) if "run" in call and call[-1] == "migrate")
    check = next(i for i, call in enumerate(calls) if "--check-heads" in call)
    assert "--no-deps" in calls[check] and "--pull" in calls[check]
    assert "never" in calls[check] and "--entrypoint" in calls[check]
    barrier = next(i for i, call in enumerate(calls) if "scripts.wait_for_migration" in call)
    assert migration < barrier < check
    assert state["running_at_migration_barrier"] == {}
    assert REVISION in state["migration_barrier_image"]
    starts = [
        i
        for i, call in enumerate(calls)
        if ("start" in call or "up" in call) and "docker-compose.yml" in call
    ]
    assert starts and all(check < i for i in starts)


@pytest.mark.parametrize("failure", ["backup", "init", "pause-apps"])
def test_recovery_before_migration_does_not_require_schema_probe(release_environment, failure):
    _, state_path, environment = release_environment
    result = run_release(
        {**environment, "DEPLOY_TEST_FAILURE": failure, "DEPLOY_TEST_SCHEMA_CHECK": "unavailable"}
    )
    assert result.returncode != 0
    state = json.loads(state_path.read_text())
    assert not any("--check-heads" in call for call in state["calls"])
    assert not any("scripts.wait_for_migration" in call for call in state["calls"])
    assert state["running"] == {
        "backend": "previous-backend",
        "frontend": "previous-frontend",
        "notification-worker": "previous-backend",
    }


def test_recovery_terminates_exact_leftover_migration_before_schema_check(release_environment):
    _, state_path, environment = release_environment
    result = run_release(
        {**environment, "DEPLOY_TEST_FAILURE": "migrate", "DEPLOY_TEST_MIGRATION_LEFTOVER": "1"}
    )
    assert result.returncode == 46, result.stderr
    calls = json.loads(state_path.read_text())["calls"]
    removal = next(i for i, call in enumerate(calls) if call[:3] == ["docker", "rm", "--force"])
    assert calls[removal][-1] == f"garment-buro-production-migrate-{REVISION}"
    check = next(i for i, call in enumerate(calls) if "--check-heads" in call)
    assert removal < check


@pytest.mark.parametrize("failure", ["INSPECT", "REMOVE"])
def test_unverified_migration_termination_keeps_old_writers_stopped(release_environment, failure):
    _, state_path, environment = release_environment
    result = run_release(
        {
            **environment,
            "DEPLOY_TEST_FAILURE": "migrate",
            "DEPLOY_TEST_MIGRATION_LEFTOVER": "1",
            f"DEPLOY_TEST_MIGRATION_{failure}_FAIL": "1",
        }
    )
    assert result.returncode == 46
    assert "manual recovery required" in result.stderr
    state = json.loads(state_path.read_text())
    assert state["running"] == {}
    assert not any(
        "--check-heads" in call or "start" in call or "up" in call for call in state["calls"]
    )


def test_failed_migration_is_removed_when_all_previous_writers_were_dormant(release_environment):
    _, state_path, environment = release_environment
    state = json.loads(state_path.read_text())
    state["running"] = {}
    state_path.write_text(json.dumps(state))
    result = run_release(
        {**environment, "DEPLOY_TEST_FAILURE": "migrate", "DEPLOY_TEST_MIGRATION_LEFTOVER": "1"}
    )
    assert result.returncode == 46
    state = json.loads(state_path.read_text())
    assert ["docker", "rm", "--force", f"garment-buro-production-migrate-{REVISION}"] in state[
        "calls"
    ]
    assert state["running"] == {}
    assert not any(
        "--check-heads" in call or "start" in call or "up" in call for call in state["calls"]
    )


@pytest.mark.parametrize("failure", ["migrate", "http", "workers", "metadata"])
def test_unfinished_postgres_transaction_blocks_previous_writers(release_environment, failure):
    deployment, state_path, environment = release_environment
    before = (deployment / ".release").read_bytes()
    result = run_release(
        {
            **environment,
            "DEPLOY_TEST_FAILURE": failure,
            "DEPLOY_TEST_MIGRATION_BARRIER_FAIL": "1",
        }
    )
    assert result.returncode != 0
    assert "Cannot confirm PostgreSQL migration completion" in result.stderr
    state = json.loads(state_path.read_text())
    assert state["running"] == {}
    assert not any("--check-heads" in call for call in state["calls"])
    calls = state["calls"]
    barrier = next(i for i, call in enumerate(calls) if "scripts.wait_for_migration" in call)
    assert not any("start" in call or "up" in call for call in calls[barrier + 1 :])
    assert calls[-1] == [
        "docker",
        "rm",
        "--force",
        f"garment-buro-production-migration-idle-{REVISION}",
    ]
    assert (deployment / ".release").read_bytes() == before
