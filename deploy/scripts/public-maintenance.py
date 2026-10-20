#!/usr/bin/env python3
"""Own a persistent Nginx maintenance marker and verify every public entry point.

The deployment caller holds .deploy.lock. This tool also serializes manual gate
operations. It never changes application containers or restores database data.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import secrets
import signal
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

PROBE_PATH = "/_garment/deployment-gate"
ORIGINS = {
    "production": (
        "https://garment-buro.ru",
        "https://www.garment-buro.ru",
        "https://partner.garment-buro.ru",
        "https://production.garment-buro.ru",
    ),
    "development": ("https://dev.garment-buro.ru",),
}


class GateError(RuntimeError):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_origins(root: Path, environment: str) -> tuple[str, ...]:
    path = root / environment / "public-origins.txt"
    if path.exists():
        values = tuple(
            line.strip() for line in path.read_text().splitlines() if line.strip()
        )
    else:
        values = ORIGINS[environment]
    normalized = tuple(value.rstrip("/") for value in values)
    if not 1 <= len(values) <= 16 or len(set(normalized)) != len(values):
        raise GateError("Configure a unique, nonempty public origins list (maximum 16)")
    for value in values:
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
                and not any(char.isspace() for char in value)
            )
            _ = (
                parsed.port
            )  # Validate malformed/out-of-range ports before any mutation.
        except ValueError:
            valid = False
        if not valid:
            raise GateError(
                "Public origins must be HTTPS origins without credentials or paths"
            )
    return normalized


def verify(origins: tuple[str, ...], environment: str, closed: bool) -> None:
    opener = build_opener(ProxyHandler({}), NoRedirects())
    for origin in origins:
        request = Request(
            origin + PROBE_PATH + "?probe=" + secrets.token_hex(12),
            headers={
                "Cache-Control": "no-cache, no-store",
                "User-Agent": "garment-release-gate/1",
            },
        )
        try:
            try:
                response = opener.open(request, timeout=8)
            except HTTPError as error:
                response = error
            with response:
                correct = response.code == (503 if closed else 204)
                correct &= (
                    response.headers.get("X-Garment-Deployment-Gate")
                    == environment + "/1"
                )
                correct &= (
                    "no-store" in response.headers.get("Cache-Control", "").lower()
                )
                if closed:
                    correct &= response.headers.get("Retry-After") == "60"
                if not correct:
                    raise GateError(
                        "Public Nginx gate did not confirm the requested state"
                    )
        except (URLError, OSError, TimeoutError) as error:
            raise GateError(
                "Public Nginx gate is unreachable or its TLS validation failed"
            ) from error


def marker_owner(marker: Path) -> str | None:
    if marker.is_symlink():
        raise GateError("Refusing a symlink maintenance marker")
    try:
        return marker.read_text()
    except FileNotFoundError:
        return None


def create_marker(marker: Path, owner: str) -> None:
    try:
        descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise GateError(
            "Maintenance is already owned; inspect recovery before reopening"
        ) from error
    with os.fdopen(descriptor, "w") as stream:
        stream.write(owner)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(marker.parent)


def sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def control_directory(root: Path):
    directory = root / "maintenance"
    if directory.is_symlink():
        raise GateError("Refusing a symlink maintenance directory")
    directory.mkdir(mode=0o755, exist_ok=True)
    stat = directory.stat()
    if stat.st_uid != os.getuid() or stat.st_mode & 0o022:
        raise GateError(
            "Maintenance directory must be owned by the deployment user and not writable by others"
        )
    # The deploy script's umask is 077. Nginx needs traversal/stat, never marker contents.
    directory.chmod(0o755)
    descriptor = os.open(
        directory / ".control.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise GateError("Another public gate operation is active") from error
        yield directory
    finally:
        os.close(descriptor)


def operate(root: Path, environment: str, action: str, owner: str | None) -> None:
    origins = public_origins(root, environment)
    with control_directory(root) as directory:
        marker = directory / (environment + ".active")
        existing = marker_owner(marker)
        if action == "check-open":
            if existing is not None:
                raise GateError(
                    "Maintenance is already active; inspect the previous release first"
                )
            verify(origins, environment, False)
            return
        if owner is None or not re.fullmatch(r"[a-f0-9]{40}-[a-f0-9]{32}", owner):
            raise GateError("A release-specific owner is required")
        if action == "close":
            if existing is not None:
                raise GateError(
                    "Maintenance is already owned; inspect recovery before reopening"
                )
            create_marker(marker, owner)
            try:
                verify(origins, environment, True)
            except BaseException:
                # No application has been paused yet. Undo only this acquisition.
                if marker_owner(marker) == owner:
                    marker.unlink()
                    sync_directory(directory)
                raise
            return
        if existing not in {None, owner}:
            raise GateError("Refusing to clear another release's maintenance marker")
        try:
            if existing == owner:
                marker.unlink()
                sync_directory(directory)
            verify(origins, environment, False)
        except BaseException:
            # Some routes could already have accepted new writes. Reclose the
            # gate; the caller must keep the committed application, not roll back.
            if marker_owner(marker) is None:
                create_marker(marker, owner)
            raise


def interrupted(signum, frame):
    raise SystemExit(128 + signum)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=ORIGINS)
    parser.add_argument("action", choices=["check-open", "close", "open"])
    parser.add_argument("--owner")
    arguments = parser.parse_args()
    for signum in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(signum, interrupted)
    root = Path(os.environ.get("GARMENT_DEPLOY_ROOT", "/srv/garment-buro"))
    try:
        operate(root, arguments.environment, arguments.action, arguments.owner)
    except (GateError, OSError, ValueError) as error:
        # Do not echo configured URLs, responses or marker owner contents.
        detail = (
            str(error)
            if isinstance(error, GateError)
            else "local control operation failed"
        )
        print("Public maintenance: " + detail, file=sys.stderr)
        return 78
    print(
        json.dumps(
            {"publicGate": arguments.action, "environment": arguments.environment}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
