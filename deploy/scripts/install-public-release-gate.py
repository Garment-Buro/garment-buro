#!/usr/bin/env python3
"""One-time root installation into the existing public proxy, preserving its routes."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pwd
import re
import secrets
import shutil
import signal
import stat
import subprocess
import tempfile
from pathlib import Path

PRODUCTION = {
    "garment-buro.ru",
    "www.garment-buro.ru",
    "partner.garment-buro.ru",
    "production.garment-buro.ru",
}
DEVELOPMENT = {"dev.garment-buro.ru"}
DOCKER = ["docker", "--host", "unix:///var/run/docker.sock"]
TOKEN = re.compile(
    r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\#[^\n]*|[{};]|[^\s{};\#]+"""
)
MOUNTS = [
    ("garment-nginx-logging/http.conf", "/etc/nginx/conf.d/00-garment-logging.conf"),
    (
        "garment-nginx-logging/server.conf",
        "/etc/nginx/garment-buro/server-logging.conf",
    ),
    (
        "garment-nginx-maintenance/server.conf",
        "/etc/nginx/garment-buro/maintenance.conf",
    ),
    ("/srv/garment-buro/maintenance", "/srv/garment-buro/maintenance"),
]


def patch_nginx(source: str) -> str:
    if (
        "garment-buro/maintenance.conf" in source
        or "garment-buro/server-logging.conf" in source
    ):
        raise ValueError(
            "Proxy already contains release includes; inspect rather than overwrite"
        )
    tokens = [m for m in TOKEN.finditer(source) if not m[0].startswith("#")]
    depth = 0
    blocks = []
    current = None
    directive = []
    for index, token in enumerate(tokens):
        value = token[0]
        if value == "{":
            if depth == 0 and index and tokens[index - 1][0] == "server":
                current = {"open": token.end(), "names": [], "listen": []}
                blocks.append(current)
            depth += 1
            directive = []
        elif value == "}":
            depth -= 1
            directive = []
            if depth == 0:
                current = None
        elif depth == 1 and current is not None:
            if value == ";":
                if directive and directive[0] == "server_name":
                    current["names"].extend(directive[1:])
                if directive and directive[0] == "listen":
                    current["listen"].extend(directive[1:])
                directive = []
            else:
                directive.append(value.strip("\"'"))
    if depth != 0:
        raise ValueError("Unbalanced Nginx configuration")
    patches = []
    covered = set()
    for block in blocks:
        names = set(block["names"])
        if not names & (PRODUCTION | DEVELOPMENT):
            continue
        addition = "\n    include /etc/nginx/garment-buro/server-logging.conf;"
        if "ssl" in block["listen"]:
            if not names <= PRODUCTION and not names <= DEVELOPMENT:
                raise ValueError("A managed HTTPS block shares unrelated hosts")
            environment = "production" if names <= PRODUCTION else "development"
            covered.update(names)
            addition += (
                f"\n    set $garment_deployment_environment {environment};"
                "\n    include /etc/nginx/garment-buro/maintenance.conf;"
            )
        patches.append((block["open"], addition))
    required = PRODUCTION | (
        DEVELOPMENT if any(DEVELOPMENT & set(b["names"]) for b in blocks) else set()
    )
    if not required <= covered:
        raise ValueError("All managed HTTPS origins must be present")
    for position, addition in reversed(patches):
        source = source[:position] + addition + source[position:]
    return source


def patch_override(source: str) -> str:
    lines = source.splitlines(keepends=True)
    matches = [
        i for i, line in enumerate(lines) if re.fullmatch(r"  nginx:\s*\n?", line)
    ]
    if len(matches) != 1:
        raise ValueError("Expected the existing two-space nginx override block")
    start = matches[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"  [^\s#]", lines[i])),
        len(lines),
    )
    if any(re.match(r"    volumes:", line) for line in lines[start + 1 : end]):
        raise ValueError("Existing override volumes require a separate reviewed merge")
    addition = "    volumes:\n" + "".join(
        f"      - {src if src.startswith('/') else './' + src}:{dst}:ro\n"
        for src, dst in MOUNTS
    )
    lines.insert(start + 1, addition)
    return "".join(lines)


def run(args: list[str], *, log: Path | None = None) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if log:
        with log.open("a") as stream:
            stream.write(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Required proxy operation failed")
    return result.stdout.strip()


def replace(path: Path, data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".release-gate-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install(source_root: Path, revision: str) -> dict:
    if os.geteuid() != 0 or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Root and an exact source revision are required")
    root = Path("/home/plus2opacity")
    account = pwd.getpwnam("garment")
    deployment_root = Path("/srv/garment-buro")
    lock = os.open(deployment_root / ".deploy.lock", os.O_CREAT | os.O_RDWR, 0o600)
    os.fchown(lock, account.pw_uid, account.pw_gid)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    proxy = "plus2opacity-nginx-1"
    configuration = root / "nginx.conf"
    override = root / "docker-compose.override.yml"
    base = root / "docker-compose.yml"
    original = {
        p: (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
        for p in [configuration, override]
    }
    candidate = patch_nginx(original[configuration][0].decode())
    candidate_override = patch_override(original[override][0].decode())
    image = run(DOCKER + ["inspect", "--format", "{{.Config.Image}}", proxy])
    image_id = run(DOCKER + ["inspect", "--format", "{{.Image}}", proxy])
    if run(DOCKER + ["image", "inspect", "--format", "{{.Id}}", image]) != image_id:
        raise ValueError("Cached proxy tag differs from its running image")
    networks = json.loads(
        run(
            DOCKER
            + ["inspect", "--format", "{{json .NetworkSettings.Networks}}", proxy]
        )
    )
    if len(networks) != 1:
        raise ValueError("Inspect multi-network proxy before installation")
    state = deployment_root / "maintenance"
    if state.is_symlink() or list(state.glob("*.active")):
        raise ValueError("Resolve existing maintenance ownership before installation")
    backup = Path(tempfile.mkdtemp(prefix="garment-release-proxy-", dir="/root"))
    backup.chmod(0o700)
    log = backup / "operations.log"
    for path, (data, mode) in original.items():
        replace(backup / path.name, data, mode & 0o600)
    stage = backup / "candidate"
    stage.mkdir()
    (stage / "nginx.conf").write_text(candidate)
    sources = {
        "garment-nginx-logging/http.conf": source_root / "logging/http.conf",
        "garment-nginx-logging/server.conf": source_root / "logging/server.conf",
        "garment-nginx-maintenance/server.conf": source_root
        / "maintenance/server.conf",
    }
    for relative, source in sources.items():
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        existing = root / relative
        if existing.exists():
            saved = backup / "previous-includes" / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(existing, saved)
    state.mkdir(mode=0o755, exist_ok=True)
    os.chown(state, account.pw_uid, account.pw_gid)
    state.chmod(0o755)
    old_parent_mode = stat.S_IMODE(deployment_root.stat().st_mode)
    deployment_root.chmod(old_parent_mode | 0o001)
    helper = deployment_root / "production/public-maintenance.next.py"
    helper_previous = helper.read_bytes() if helper.exists() else None
    compose = DOCKER + [
        "compose",
        "--project-directory",
        str(root),
        "-f",
        str(base),
        "-f",
        str(override),
    ]
    owner = revision + "-" + secrets.token_hex(16)
    changed = False
    try:
        test = DOCKER + [
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            next(iter(networks)),
            "--add-host",
            "host.docker.internal:host-gateway",
            "--volumes-from",
            proxy + ":ro",
            "-v",
            f"{stage / 'nginx.conf'}:/etc/nginx/conf.d/default.conf:ro",
        ]
        for relative, destination in MOUNTS:
            source = state if relative.startswith("/") else stage / relative
            test += ["-v", f"{source}:{destination}:ro"]
        run(test + ["--entrypoint", "nginx", image_id, "-t"], log=log)
        for relative in sources:
            target = root / relative
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            replace(target, (stage / relative).read_bytes(), 0o644)
        replace(helper, (source_root / "public-maintenance.py").read_bytes(), 0o750)
        os.chown(helper, account.pw_uid, account.pw_gid)
        changed = True
        replace(configuration, candidate.encode(), original[configuration][1])
        replace(override, candidate_override.encode(), original[override][1])
        run(compose + ["config", "--quiet"], log=log)
        run(
            compose
            + ["up", "-d", "--no-deps", "--pull", "never", "--force-recreate", "nginx"],
            log=log,
        )
        run(DOCKER + ["exec", proxy, "nginx", "-t"], log=log)
        gate = ["runuser", "-u", "garment", "--", "python3", str(helper), "production"]
        run(gate + ["check-open"], log=log)
        run(gate + ["close", "--owner", owner], log=log)
        run(gate + ["open", "--owner", owner], log=log)
    except BaseException:  # noqa: BLE001 - restore the proxy on errors and handled signals
        if changed:
            for path, (data, mode) in original.items():
                replace(path, data, mode)
            run(
                compose
                + [
                    "up",
                    "-d",
                    "--no-deps",
                    "--pull",
                    "never",
                    "--force-recreate",
                    "nginx",
                ],
                log=log,
            )
        marker = state / "production.active"
        if marker.exists() and marker.read_text() == owner:
            marker.unlink()
        if helper_previous is not None:
            replace(helper, helper_previous, 0o750)
            os.chown(helper, account.pw_uid, account.pw_gid)
        elif helper.exists():
            helper.unlink()
        for relative in sources:
            saved = backup / "previous-includes" / relative
            if saved.exists():
                replace(
                    root / relative,
                    saved.read_bytes(),
                    stat.S_IMODE(saved.stat().st_mode),
                )
        deployment_root.chmod(old_parent_mode)
        raise RuntimeError(
            f"Proxy preparation failed; private recovery directory: {backup}"
        ) from None
    return {
        "publicProxyPrepared": True,
        "productionCloseOpenPassed": True,
        "backup": str(backup),
        "sourceRevision": revision,
        "applicationContainersChanged": False,
    }


if __name__ == "__main__":

    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    for handled_signal in [signal.SIGTERM, signal.SIGHUP]:
        signal.signal(handled_signal, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    arguments = parser.parse_args()
    print(json.dumps(install(arguments.source_root, arguments.revision)))
