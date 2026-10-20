from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("logging_state", ["complete", "partial", "empty", "absent"])
@pytest.mark.parametrize("fail_reload", [True, False])
@pytest.mark.parametrize("had_maintenance", [True, False])
def test_public_host_logging_install_and_rollback(
    tmp_path, logging_state, fail_reload, had_maintenance
):
    """Execute the real installer in an owned fixture; Docker cannot touch a server."""
    legacy = tmp_path / "legacy"
    widget = tmp_path / "widget"
    binary = tmp_path / "bin"
    for folder in (legacy, widget, binary):
        folder.mkdir()
    (legacy / "nginx.conf").write_text("previous vhosts")
    (legacy / "docker-compose.yml").touch()
    (legacy / "docker-compose.override.yml").write_text("previous override")
    (widget / "docker-compose.server.yml").touch()
    logging = legacy / "garment-nginx-logging"
    maintenance = legacy / "garment-nginx-maintenance"
    if had_maintenance:
        maintenance.mkdir()
        (maintenance / "server.conf").write_text("previous maintenance policy")
    control = tmp_path / "maintenance"
    control.mkdir()
    (control / "production.active").write_text("a retained gate")
    if logging_state != "absent":
        logging.mkdir()
    if logging_state in ("complete", "partial"):
        (logging / "http.conf").write_text("previous http policy")
    if logging_state == "complete":
        (logging / "server.conf").write_text("previous server policy")
    docker = binary / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\nset -eu\n"
        'if [[ "$*" == "compose up -d --force-recreate nginx" && '
        '"${FIXTURE_FAIL}" == 1 && ! -f "${FIXTURE_FAILED}" ]]; then\n'
        '  touch "${FIXTURE_FAILED}"; exit 19\nfi\n'
        # Validate both new mount sources during the preflight call.
        'if [[ "${1}" == run ]]; then\n'
        '  [[ "$*" == *"${FIXTURE_SOURCE}/deploy/nginx/logging/http.conf:/etc/nginx/conf.d/00-garment-logging.conf:ro"* ]]\n'
        '  [[ "$*" == *"${FIXTURE_SOURCE}/deploy/nginx/logging/server.conf:/etc/nginx/garment-buro/server-logging.conf:ro"* ]]\n'
        '  test -f "${FIXTURE_SOURCE}/deploy/nginx/logging/http.conf"\n'
        '  test -f "${FIXTURE_SOURCE}/deploy/nginx/logging/server.conf"\nfi\n'
    )
    docker.chmod(0o755)
    # Only paths and the root-only check are replaced for this local fixture.
    # All installer commands, writes, traps and rollback logic execute unchanged.
    source = (ROOT / "deploy/scripts/enable-public-hosts.sh").read_text()
    source = source.replace("if [[ ${EUID:-$(id -u)} -ne 0 ]]; then", "if false; then")
    source = source.replace("legacy_root=/home/plus2opacity", f"legacy_root={legacy}")
    source = source.replace("widget_root=/home/garment-widget", f"widget_root={widget}")
    source = source.replace(
        "maintenance_state=/srv/garment-buro/maintenance", f"maintenance_state={control}"
    )
    source = source.replace(
        'backup_dir="/root/garment-buro-nginx-backup-$(date -u +%Y%m%dT%H%M%SZ)"',
        f'backup_dir="{tmp_path}/backup"',
    )
    script = tmp_path / "install.sh"
    script.write_text(source)
    environment = {
        **os.environ,
        "PATH": f"{binary}:/usr/bin:/bin",
        "FIXTURE_FAIL": "1" if fail_reload else "0",
        "FIXTURE_FAILED": str(tmp_path / "failed-once"),
        "FIXTURE_SOURCE": str(ROOT),
    }
    result = subprocess.run(
        ["bash", str(script), str(ROOT)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if fail_reload:
        assert result.returncode == 19, result.stderr
        assert (legacy / "nginx.conf").read_text() == "previous vhosts"
        assert (legacy / "docker-compose.override.yml").read_text() == "previous override"
        if logging_state in ("complete", "partial"):
            assert (logging / "http.conf").read_text() == "previous http policy"
        else:
            assert not (logging / "http.conf").exists()
        if logging_state == "complete":
            assert (logging / "server.conf").read_text() == "previous server policy"
        else:
            assert not (logging / "server.conf").exists()
        if logging_state == "absent":
            assert not logging.exists()
        if had_maintenance:
            assert (maintenance / "server.conf").read_text() == "previous maintenance policy"
        else:
            assert not maintenance.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert (legacy / "nginx.conf").read_bytes() == (ROOT / "nginx.conf").read_bytes()
        for name in ("http.conf", "server.conf"):
            assert (logging / name).read_bytes() == (
                ROOT / "deploy/nginx/logging" / name
            ).read_bytes()
        assert "00-garment-logging.conf" in (legacy / "docker-compose.override.yml").read_text()
        assert (maintenance / "server.conf").read_bytes() == (
            ROOT / "deploy/nginx/maintenance/server.conf"
        ).read_bytes()
        assert (
            "/srv/garment-buro/maintenance:ro"
            in (legacy / "docker-compose.override.yml").read_text()
        )
    assert (control / "production.active").read_text() == "a retained gate"
