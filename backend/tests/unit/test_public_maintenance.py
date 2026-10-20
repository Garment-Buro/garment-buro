from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

ROOT = Path(__file__).resolve().parents[3]
OWNER = "a" * 40 + "-" + "b" * 32
OTHER = "c" * 40 + "-" + "d" * 32


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location(
        "public_gate", ROOT / "deploy/scripts/public-maintenance.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_ownership_and_environment_isolation(gate, tmp_path, monkeypatch):
    probes = []
    monkeypatch.setattr(gate, "verify", lambda origins, env, closed: probes.append((env, closed)))
    gate.operate(tmp_path, "production", "check-open", None)
    gate.operate(tmp_path, "production", "close", OWNER)
    marker = tmp_path / "maintenance/production.active"
    assert marker.read_text() == OWNER
    assert marker.stat().st_mode & 0o777 == 0o600
    with pytest.raises(gate.GateError, match="already"):
        gate.operate(tmp_path, "production", "check-open", None)
    with pytest.raises(gate.GateError, match="another release"):
        gate.operate(tmp_path, "production", "open", OTHER)
    gate.operate(tmp_path, "development", "close", OTHER)
    gate.operate(tmp_path, "production", "open", OWNER)
    assert not marker.exists()
    assert (tmp_path / "maintenance/development.active").read_text() == OTHER
    assert probes == [
        ("production", False),
        ("production", True),
        ("development", True),
        ("production", False),
    ]


@pytest.mark.parametrize("action", ["close", "open"])
def test_failed_public_confirmation_cleans_acquisition_or_recloses(
    gate, tmp_path, monkeypatch, action
):
    marker = tmp_path / "maintenance/production.active"
    if action == "open":
        marker.parent.mkdir()
        marker.write_text(OWNER)

    def fail(*args):
        raise gate.GateError("a public origin did not confirm")

    monkeypatch.setattr(gate, "verify", fail)
    with pytest.raises(gate.GateError):
        gate.operate(tmp_path, "production", action, OWNER)
    assert marker.exists() == (action == "open")
    if marker.exists():
        assert marker.read_text() == OWNER


def test_foreign_gate_and_symlink_are_never_cleared(gate, tmp_path, monkeypatch):
    directory = tmp_path / "maintenance"
    directory.mkdir()
    unrelated = tmp_path / "unrelated"
    unrelated.write_text("keep me")
    marker = directory / "production.active"
    marker.symlink_to(unrelated)
    monkeypatch.setattr(
        gate, "verify", lambda *args: pytest.fail("Unowned gate reached public probe")
    )
    for action in ["check-open", "close", "open"]:
        with pytest.raises(gate.GateError, match="symlink"):
            gate.operate(tmp_path, "production", action, OWNER)
    assert unrelated.read_text() == "keep me"


def test_error_after_unlink_recloses_the_owned_gate(gate, tmp_path, monkeypatch):
    marker = tmp_path / "maintenance/production.active"
    marker.parent.mkdir()
    marker.write_text(OWNER)
    attempts = []

    def fail_once(directory):
        attempts.append(directory)
        if len(attempts) == 1:
            raise OSError("fixture durability failure")

    monkeypatch.setattr(gate, "sync_directory", fail_once)
    monkeypatch.setattr(
        gate, "verify", lambda *args: pytest.fail("Unlink failure reached HTTP probe")
    )
    with pytest.raises(OSError, match="durability failure"):
        gate.operate(tmp_path, "production", "open", OWNER)
    assert marker.read_text() == OWNER


@pytest.mark.parametrize(
    "value",
    [
        "",
        "http://example.org",
        "https://user:pass@example.org",
        "https://example.org/api",
        "https://example.org?secret=1",
        "https://example.org#fragment",
        "https://example.org:bad",
        "https://example.org\nhttps://example.org/",
    ],
)
def test_invalid_origins_fail_before_gate_mutation(gate, tmp_path, value):
    deployment = tmp_path / "production"
    deployment.mkdir()
    (deployment / "public-origins.txt").write_text(value)
    with pytest.raises(gate.GateError):
        gate.operate(tmp_path, "production", "close", OWNER)
    assert not (tmp_path / "maintenance").exists()


@pytest.mark.parametrize("closed", [False, True])
def test_public_probe_checks_every_origin_and_accepts_real_http_error(gate, monkeypatch, closed):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            headers = {
                "X-Garment-Deployment-Gate": "production/1",
                "Cache-Control": "no-store",
                "Retry-After": "60",
            }
            # HTTPError is the actual urllib response type for an expected 503.
            response = HTTPError(request.full_url, 503 if closed else 204, "fixture", headers, None)
            if closed:
                raise response
            return response

    monkeypatch.setattr(gate, "build_opener", lambda *args: Opener())
    gate.verify(("https://one.test", "https://two.test"), "production", closed)
    assert len(calls) == 2 and calls[0].startswith("https://one.test/_garment/")
    assert calls[1].startswith("https://two.test/_garment/")
    assert calls[0].split("?probe=")[1] != calls[1].split("?probe=")[1]


@pytest.mark.parametrize(
    "status,header,cache,retry",
    [
        (200, "production/1", "no-store", "60"),
        (302, "production/1", "no-store", "60"),
        (503, "development/1", "no-store", "60"),
        (503, "production/1", "public", "60"),
        (503, "production/1", "no-store", ""),
    ],
)
def test_generic_upstream_failure_or_wrong_gate_is_rejected(
    gate, monkeypatch, status, header, cache, retry
):
    class Opener:
        def open(self, request, timeout):
            raise HTTPError(
                request.full_url,
                status,
                "fixture",
                {"X-Garment-Deployment-Gate": header, "Cache-Control": cache, "Retry-After": retry},
                None,
            )

    monkeypatch.setattr(gate, "build_opener", lambda *args: Opener())
    with pytest.raises(gate.GateError, match="did not confirm"):
        gate.verify(("https://fixture.test",), "production", True)


def test_network_failure_is_sanitized(gate, monkeypatch):
    class Opener:
        def open(self, request, timeout):
            raise URLError("sensitive fixture diagnostic")

    monkeypatch.setattr(gate, "build_opener", lambda *args: Opener())
    with pytest.raises(gate.GateError) as caught:
        gate.verify(("https://fixture.test",), "production", False)
    assert "sensitive" not in str(caught.value)
