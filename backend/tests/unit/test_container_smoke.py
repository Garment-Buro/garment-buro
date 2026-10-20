"""HTTP checks are real; command lifecycle tests do not prove Docker execution."""

from __future__ import annotations

import importlib.util
import json
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "container_smoke", ROOT / "deploy/scripts/smoke-containers.py"
)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


@pytest.fixture
def http_runtime():
    responses = {
        "/health/ready": (
            200,
            "application/json",
            json.dumps(
                {
                    "status": "ready",
                    "database": "postgresql",
                    "storage": "minio",
                }
            ),
        ),
        **{
            path: (200, "application/json", '{"items":[],"next_cursor":null}')
            for path in (
                "/api/catalog/products?limit=1",
                "/api/people?limit=1",
                "/api/communities?limit=1",
            )
        },
        **{
            path: (401, "application/json", '{"detail":"unauthorized"}')
            for path in (
                "/api/profile/projects",
                "/api/profile/favorites",
                "/api/auth/orders?limit=1",
            )
        },
        "/api/settings": (404, "application/json", '{"detail":"not found"}'),
        **{
            path: (
                200,
                "text/html",
                '<script src="/_next/static/app.js"></script>'
                '<link rel="stylesheet" href="/_next/static/app.css">',
            )
            for path in ("/", "/catalog")
        },
        "/_next/static/app.js": (200, "application/javascript", "console.log('fixture')"),
        "/_next/static/app.css": (200, "text/css", "body{}"),
        **{
            smoke.image_optimizer_path(source): (
                400,
                "text/plain",
                "Image source is not public.",
                {"Cache-Control": "private, no-store"},
            )
            for source in (
                "/api/design-media/" + "Q" * 43 + "/content",
                "/api/profile/project-media/1/access",
                "/storage/private/image.png?X-Amz-Signature=synthetic",
                "/uploads/%2e%2e%2fapi/design-media/" + "Q" * 43 + "/content",
            )
        },
        smoke.image_optimizer_path("/pwa-icon-192.png"): (200, "image/webp", "fixture"),
    }
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_PUT(self):
            seen.append(self.path)
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"payload": payload, "content_type": self.headers["Content-Type"]}
                ).encode()
            )

        def do_GET(self):
            seen.append(self.path)
            status, content_type, body, *headers = responses[self.path]
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            for name, value in (headers[0] if headers else {}).items():
                self.send_header(name, value)
            if status == 302:
                self.send_header("Location", "/must-not-be-followed")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", responses, seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_runtime_checks_rewrites_auth_and_compiled_assets(http_runtime):
    base, _, seen = http_runtime
    smoke.verify_http(base, base)
    assert seen.count("/api/catalog/products?limit=1") == 2
    assert "/_next/static/app.js" in seen and "/_next/static/app.css" in seen


@pytest.mark.parametrize(
    "path,replacement",
    [
        (
            "/health/ready",
            (
                200,
                "application/json",
                '{"status":"ready","database":"disabled","storage":"disabled"}',
            ),
        ),
        ("/api/people?limit=1", (200, "text/html", "<html>wrong proxy</html>")),
        (
            "/api/communities?limit=1",
            (200, "application/json", '{"items":[{"demo":true}],"next_cursor":null}'),
        ),
        ("/api/profile/projects", (200, "application/json", "[]")),
        ("/_next/static/app.js", (200, "text/html", "<html>fallback</html>")),
        ("/_next/static/app.css", (404, "text/plain", "missing")),
        ("/catalog", (200, "text/html", "<html>no assets</html>")),
    ],
)
def test_http_runtime_rejects_broken_release(http_runtime, path, replacement):
    base, responses, _ = http_runtime
    responses[path] = replacement
    with pytest.raises((smoke.SmokeFailure, ValueError)):
        smoke.verify_http(base, base)


def test_http_does_not_follow_redirects(http_runtime):
    base, responses, seen = http_runtime
    responses["/catalog"] = (302, "text/html", "redirect")
    with pytest.raises(smoke.SmokeFailure, match="redirect"):
        smoke.request(base, "/catalog")
    assert "/must-not-be-followed" not in seen


def test_cart_probe_sends_json_put_and_requires_uncached_response(http_runtime):
    base, _, seen = http_runtime
    body, content_type = smoke.request(
        base, "/api/cart/fixture-probe", method="PUT", payload={"items": []}, no_store=True
    )
    assert "application/json" in content_type
    assert json.loads(body) == {"payload": {"items": []}, "content_type": "application/json"}
    assert seen == ["/api/cart/fixture-probe"]


def test_cart_probe_error_does_not_log_bearer_capability(http_runtime):
    base, responses, _ = http_runtime
    capability = "synthetic-private-cart-capability"
    responses["/api/cart/" + capability] = (404, "application/json", "{}")
    with pytest.raises(smoke.SmokeFailure) as failure:
        smoke.request(base, "/api/cart/" + capability)
    assert capability not in str(failure.value)
    assert "/api/cart/{cart_id}" in str(failure.value)


@pytest.mark.parametrize(
    "replacement",
    [
        (200, "image/webp", "private bytes", {"Cache-Control": "public, max-age=14400"}),
        (400, "text/plain", "rejected"),
        (400, "text/plain", "rejected", {"Cache-Control": "public, no-store"}),
        (400, "text/plain", "Q" * 43, {"Cache-Control": "private, no-store"}),
    ],
)
def test_runtime_gate_rejects_public_cache_and_reflected_private_image_url(
    http_runtime, replacement
):
    base, responses, _ = http_runtime
    responses[smoke.image_optimizer_path("/api/design-media/" + "Q" * 43 + "/content")] = (
        replacement
    )
    with pytest.raises(smoke.SmokeFailure):
        smoke.verify_image_boundary(base)


def test_runtime_gate_requires_working_public_image_optimization(http_runtime):
    base, responses, _ = http_runtime
    responses[smoke.image_optimizer_path("/pwa-icon-192.png")] = (200, "text/html", "fallback")
    with pytest.raises(smoke.SmokeFailure, match="Public image"):
        smoke.verify_image_boundary(base)


def test_container_environment_and_project_are_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "production")
    monkeypatch.setenv("COMPOSE_FILE", "/private/production.yml")
    monkeypatch.setenv("PAYMENT_CREATION_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "host-secret-must-not-leak")
    monkeypatch.setenv("DATABASE_URL", "postgresql://production")
    first_dir, second_dir = tmp_path / "first", tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = smoke.ContainerSmoke(first_dir, "backend:ci", "frontend:ci")
    second = smoke.ContainerSmoke(second_dir, "backend:ci", "frontend:ci")
    assert first.project.startswith("garment-smoke-") and first.project != second.project
    assert "COMPOSE_PROJECT_NAME" not in first.environment
    assert "COMPOSE_FILE" not in first.environment
    assert "PAYMENT_CREATION_ENABLED" not in first.environment
    assert "DATABASE_URL" not in first.environment
    assert first.environment["JWT_SECRET"] != "host-secret-must-not-leak"
    assert first.environment["FRONTEND_HOST_PORT"] == "0"
    assert first.environment["HOST_BIND_ADDRESS"] == "127.0.0.1"
    assert first.environment["DATABASE_APP_PASSWORD"] != second.environment["DATABASE_APP_PASSWORD"]
    assert (first_dir / ".env").stat().st_mode & 0o777 == 0o600
    assert (first_dir / "docker-compose.yml").read_bytes() == (
        ROOT / "deploy/docker-compose.server.yml"
    ).read_bytes()


def test_smoke_settings_enable_read_flows_without_external_operations():
    from app.core.config import Settings

    values = {key.lower(): value for key, value in smoke.smoke_environment("b:ci", "f:ci").items()}
    settings = Settings(
        _env_file=None,
        **values,
        database_enabled=True,
        database_url="postgresql+asyncpg://smoke@postgres/container_smoke",
    )
    assert settings.catalog_reads_enabled and settings.identity_api_enabled
    assert settings.carts_v2_enabled
    assert settings.minio_enabled and settings.minio_endpoint == "minio:9000"
    assert settings.order_reads_enabled and settings.partner_program_enabled
    assert not settings.checkout_v2_enabled
    assert not settings.payment_creation_enabled and not settings.fulfillment_cdek_enabled


@pytest.mark.parametrize(
    "storage_image",
    ["garment-buro-minio:2025-10-15-garment1", "storage.test/minio@sha256:" + "a" * 64],
)
def test_runtime_uses_explicit_storage_image_without_inheriting_host_choice(
    tmp_path, monkeypatch, storage_image
):
    monkeypatch.setenv("MINIO_IMAGE", "unrelated-host-storage:latest")
    runtime = smoke.ContainerSmoke(tmp_path, "backend:ci", "frontend:ci", minio_image=storage_image)
    assert runtime.environment["MINIO_IMAGE"] == storage_image
    assert "MINIO_IMAGE=" + storage_image + "\n" in (tmp_path / ".env").read_text()


def test_compose_failure_names_only_known_init_job_without_transport_output(tmp_path, monkeypatch):
    runtime = smoke.ContainerSmoke(tmp_path, "backend:ci", "frontend:ci")
    private = runtime.environment["POSTGRES_PASSWORD"]
    monkeypatch.setattr(
        smoke.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=private, stderr=private),
    )
    with pytest.raises(smoke.SmokeFailure) as failure:
        runtime.compose("run", "--rm", "--no-deps", "-T", "database-role-init")
    assert str(failure.value) == "Compose run database-role-init failed (exit 1)"
    assert private not in str(failure.value)


@pytest.mark.parametrize("failure", ["none", "config", "up", "run", "exec", "http", "cart"])
def test_command_failures_always_clean_only_owned_project(tmp_path, monkeypatch, failure):
    runtime = smoke.ContainerSmoke(tmp_path, "backend:ci", "frontend:ci")
    calls = []

    def compose(*args, **_kwargs):
        calls.append(args)
        if args[0] == failure:
            raise smoke.SmokeFailure("injected failure")
        if args[0] == "port":
            return "127.0.0.1:12345"
        return ""

    def verify(*_args):
        if failure == "http":
            raise smoke.SmokeFailure("injected HTTP failure")

    monkeypatch.setattr(runtime, "compose", compose)
    monkeypatch.setattr(smoke, "verify_http", verify)

    def verify_cart(*_args):
        if failure == "cart":
            raise smoke.SmokeFailure("injected cart failure")

    monkeypatch.setattr(runtime, "verify_persistent_cart", verify_cart)
    if failure == "none":
        runtime.run()
        assert sum(call[-1] == "migrate" for call in calls) == 2
    else:
        with pytest.raises(smoke.SmokeFailure, match="injected"):
            runtime.run()
    assert calls[-1] == ("down", "--volumes", "--remove-orphans", "--timeout", "20")
    assert runtime.cleaned
    assert runtime.command[runtime.command.index("--project-name") + 1] == runtime.project


def test_failed_cleanup_retains_private_config_for_recovery(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(smoke.shutil, "which", lambda _name: "/docker")
    monkeypatch.setattr(smoke.tempfile, "mkdtemp", lambda **_kwargs: str(tmp_path))
    monkeypatch.setattr(smoke.sys, "argv", ["smoke-containers.py"])

    def failing_command(*_args, **_kwargs):
        raise smoke.SmokeFailure("injected transport failure")

    monkeypatch.setattr(smoke.ContainerSmoke, "compose", failing_command)
    assert smoke.main() == 1
    assert (tmp_path / ".env").exists()
    output = capsys.readouterr().err
    assert "Cleanup incomplete for garment-smoke-" in output
    env_text = (tmp_path / ".env").read_text()
    for line in env_text.splitlines():
        key, value = line.split("=", 1)
        if any(word in key for word in ("SECRET", "PASSWORD", "PEPPER", "ENCRYPTION")):
            assert value not in output


def test_sigterm_cleans_owned_project_and_restores_handlers(tmp_path, monkeypatch):
    monkeypatch.setattr(smoke.shutil, "which", lambda _name: "/docker")
    monkeypatch.setattr(smoke.tempfile, "mkdtemp", lambda **_kwargs: str(tmp_path))
    monkeypatch.setattr(smoke.sys, "argv", ["smoke-containers.py"])
    previous = signal.getsignal(signal.SIGTERM)
    calls = []

    def compose(_self, *args, **_kwargs):
        calls.append(args)
        return "127.0.0.1:12345" if args[0] == "port" else ""

    def interrupted_http(*_args):
        signal.raise_signal(signal.SIGTERM)

    monkeypatch.setattr(smoke.ContainerSmoke, "compose", compose)
    monkeypatch.setattr(smoke, "verify_http", interrupted_http)
    assert smoke.main() == 1
    assert calls[-1][0] == "down"
    assert not tmp_path.exists()
    assert signal.getsignal(signal.SIGTERM) == previous


@pytest.mark.parametrize("failure", ["none", "none-shared", "redis-running", "cart-lost"])
def test_cart_gate_restarts_api_without_redis(tmp_path, monkeypatch, failure):
    runtime = smoke.ContainerSmoke(tmp_path, "backend:test", "frontend:test")
    state = {"redis": True, "restarted": False, "saved": None, "reads_after_restart": 0}
    recovered_bases = []

    def compose(*args, **_kwargs):
        if args[0] == "exec":
            return "42"
        if args[0] == "stop":
            state["redis"] = False
        if args[0] in {"start", "up"}:
            # Real Compose start traverses depends_on, even for a selected API.
            state["restarted"] = True
            state["redis"] = "--no-deps" not in args or failure == "redis-running"
        if args[0] == "ps":
            return "redis" if state["redis"] else ""
        if args[0] == "port":
            return "127.0.0.1:12346"
        return ""

    def request(_base, _path, **kwargs):
        assert kwargs["no_store"]
        if kwargs.get("expected") == 409:
            body = {"detail": {"code": "cart_conflict"}}
        elif kwargs.get("method") == "PUT":
            state["saved"] = {
                "revision": "a" * 32,
                "items": [
                    {
                        "product_id": 42,
                        "quantity": 2,
                        "price": 1580,
                        "customization": {"totalPrice": 1580},
                    }
                ],
            }
            body = state["saved"]
        else:
            if state["restarted"]:
                state["reads_after_restart"] += 1
                # Random host bindings can change even without container recreation.
                if _base == "http://backend.invalid":
                    raise smoke.SmokeFailure("Old backend binding is closed")
                recovered_bases.append(_base)
            body = state["saved"]
            if body is None or (state["restarted"] and failure == "cart-lost"):
                body = {"revision": None, "items": []}
        return json.dumps(body).encode(), "application/json"

    monkeypatch.setattr(runtime, "compose", compose)
    monkeypatch.setattr(smoke, "request", request)
    frontend = "http://backend.invalid" if failure == "none-shared" else "http://frontend.invalid"
    if failure in {"none", "none-shared"}:
        runtime.verify_persistent_cart("http://backend.invalid", frontend)
        assert state["restarted"] and not state["redis"]
        assert state["reads_after_restart"] == 2
        assert recovered_bases == [
            "http://127.0.0.1:12346",
            "http://127.0.0.1:12346" if failure == "none-shared" else frontend,
        ]
    else:
        message = "Redis is running" if failure == "redis-running" else "cart was lost"
        with pytest.raises(smoke.SmokeFailure, match=message):
            runtime.verify_persistent_cart("http://backend.invalid", frontend)
