#!/usr/bin/env python3
"""Start disposable release images with the real server descriptor; never deploy."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MINIO_IMAGE = "garment-buro-minio:2025-10-15-garment1"


class SmokeFailure(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SmokeFailure("Unexpected HTTP redirect")


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets: set[str] = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        url = values.get("src") if tag == "script" else values.get("href")
        if (
            tag in {"script", "link"}
            and url
            and url.startswith("/_next/static/")
            and re.search(r"\.(js|css)(\?|$)", url)
        ):
            self.assets.add(url)


def request(
    base: str,
    path: str,
    expected: int = 200,
    *,
    no_store: bool = False,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[bytes, str]:
    # Smoke traffic must stay on the chosen loopback endpoint, including redirects.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    label = "/api/cart/{cart_id}" if path.startswith("/api/cart/") else path
    data = json.dumps(payload).encode() if payload is not None else None
    outgoing = Request(base + path, data=data, method=method)
    if data is not None:
        outgoing.add_header("Content-Type", "application/json")
    try:
        response = opener.open(outgoing, timeout=15)
    except HTTPError as error:
        response = error
    with response:
        if response.status != expected or response.geturl() != base + path:
            raise SmokeFailure(f"Unexpected HTTP response for {label}")
        cache_control = response.headers.get("Cache-Control", "").lower()
        if no_store and ("no-store" not in cache_control or "public" in cache_control):
            raise SmokeFailure("Protected response must not be cached")
        body = response.read(4_000_001)
        if len(body) > 4_000_000:
            raise SmokeFailure(f"Response exceeds smoke limit for {label}")
        return body, response.headers.get("Content-Type", "")


def image_optimizer_path(source: str) -> str:
    return "/_next/image?" + urlencode({"url": source, "w": 64, "q": 75})


def verify_image_boundary(frontend: str) -> None:
    # Synthetic marker only: never request a real customer capability in CI logs.
    marker = "Q" * 43
    for source in (
        f"/api/design-media/{marker}/content",
        "/api/profile/project-media/1/access",
        "/storage/private/image.png?X-Amz-Signature=synthetic",
        f"/uploads/%2e%2e%2fapi/design-media/{marker}/content",
    ):
        body, _ = request(frontend, image_optimizer_path(source), 400, no_store=True)
        if marker.encode() in body:
            raise SmokeFailure("Private image rejection reflects the source")
    body, content_type = request(frontend, image_optimizer_path("/pwa-icon-192.png"))
    if not body or not content_type.startswith("image/"):
        raise SmokeFailure("Public image optimization is unavailable")


def verify_http(backend: str, frontend: str) -> None:
    body, _ = request(backend, "/health/ready")
    if json.loads(body) != {
        "status": "ready",
        "database": "postgresql",
        "storage": "minio",
    }:
        raise SmokeFailure("Required runtime dependencies are not ready")

    for path in (
        "/api/catalog/products?limit=1",
        "/api/people?limit=1",
        "/api/communities?limit=1",
    ):
        for base in (backend, frontend):
            body, content_type = request(base, path)
            page = json.loads(body)
            if "application/json" not in content_type or page != {
                "items": [],
                "next_cursor": None,
            }:
                raise SmokeFailure(f"Unexpected empty database page for {path}")
    for path in (
        "/api/profile/projects",
        "/api/profile/favorites",
        "/api/auth/orders?limit=1",
    ):
        request(frontend, path, 401)
    request(frontend, "/api/settings", 404)
    verify_image_boundary(frontend)

    assets: set[str] = set()
    for path in ("/", "/catalog"):
        body, content_type = request(frontend, path)
        if "text/html" not in content_type:
            raise SmokeFailure(f"Missing standalone page for {path}")
        parser = AssetParser()
        parser.feed(body.decode("utf-8"))
        if not any(".js" in url for url in parser.assets) or not any(
            ".css" in url for url in parser.assets
        ):
            raise SmokeFailure(f"Page has no compiled JS/CSS references for {path}")
        assets.update(parser.assets)
    for path in sorted(assets):
        body, content_type = request(frontend, path)
        expected_type = "text/css" if re.search(r"\.css(\?|$)", path) else "javascript"
        if not body or expected_type not in content_type:
            raise SmokeFailure("Missing compiled standalone asset")
    print(
        f"Runtime HTTP passed: dependencies, API rewrites, auth, private images, pages, {len(assets)} assets"
    )


def smoke_environment(
    backend_image: str, frontend_image: str, minio_image: str = DEFAULT_MINIO_IMAGE
) -> dict[str, str]:
    return {
        "DEPLOY_ENV": "development",
        "APP_ENV": "staging",
        "PUBLIC_BASE_URL": "https://container-smoke.invalid",
        "BACKEND_IMAGE": backend_image,
        "FRONTEND_IMAGE": frontend_image,
        "MINIO_IMAGE": minio_image,
        "POSTGRES_DB": "container_smoke",
        "POSTGRES_USER": "smoke_owner",
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "DATABASE_APP_USER": "smoke_app",
        "DATABASE_APP_PASSWORD": secrets.token_hex(24),
        "MINIO_ACCESS_KEY": "smoke-" + secrets.token_hex(8),
        "MINIO_SECRET_KEY": secrets.token_hex(24),
        "MINIO_BUCKET_PREFIX": "container-smoke",
        "MINIO_ENABLED": "true",
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_SECURE": "false",
        "MINIO_PUBLIC_BASE_URL": "https://container-smoke.invalid/media",
        "HOST_BIND_ADDRESS": "127.0.0.1",
        "FRONTEND_HOST_PORT": "0",
        "BACKEND_HOST_PORT": "0",
        "MINIO_HOST_PORT": "0",
        "CATALOG_READS_ENABLED": "true",
        "CATALOG_WRITES_ENABLED": "true",
        "CARTS_V2_ENABLED": "true",
        "IDENTITY_API_ENABLED": "true",
        "ORDER_READS_ENABLED": "true",
        "PARTNER_PROGRAM_ENABLED": "true",
        "JWT_SECRET": secrets.token_hex(32),
        "IDENTITY_OTP_PEPPER": secrets.token_hex(32),
        "NOTIFICATION_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "PARTNER_ATTRIBUTION_SECRET": secrets.token_hex(32),
    }


class ContainerSmoke:
    def __init__(
        self,
        directory: Path,
        backend_image: str,
        frontend_image: str,
        *,
        minio_image: str = DEFAULT_MINIO_IMAGE,
    ):
        config = smoke_environment(backend_image, frontend_image, minio_image)
        env_file = directory / ".env"
        env_file.write_text("".join(f"{key}={value}\n" for key, value in config.items()))
        env_file.chmod(0o600)
        descriptor = directory / "docker-compose.yml"
        shutil.copyfile(ROOT / "deploy/docker-compose.server.yml", descriptor)
        self.project = "garment-smoke-" + secrets.token_hex(8)
        self.cleaned = False
        self.command = [
            "docker",
            "compose",
            "--project-name",
            self.project,
            "--env-file",
            str(env_file),
            "-f",
            str(descriptor),
        ]
        # Do not inherit application flags, credentials, Compose files or project names.
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "PATH",
                "HOME",
                "DOCKER_HOST",
                "DOCKER_CONTEXT",
                "DOCKER_CONFIG",
                "XDG_RUNTIME_DIR",
            }
        }
        self.environment.update(config)
        self.environment["COMPOSE_DISABLE_ENV_FILE"] = "true"

    def compose(self, *args: str, timeout: int = 240) -> str:
        result = subprocess.run(
            [*self.command, *args],
            env=self.environment,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            # No config, environment, database credentials or container logs in CI output.
            job = (
                " " + args[-1]
                if args[0] == "run" and args[-1] in {"database-role-init", "minio-init", "migrate"}
                else ""
            )
            raise SmokeFailure(f"Compose {args[0]}{job} failed (exit {result.returncode})")
        return result.stdout.strip()

    def endpoint(self, service: str, port: str) -> str:
        address = self.compose("port", service, port)
        if not re.fullmatch(r"127\.0\.0\.1:[1-9][0-9]{0,4}", address):
            raise SmokeFailure("Expected one loopback port binding")
        return "http://" + address

    def verify_persistent_cart(self, backend: str, frontend: str) -> None:
        # A real catalog row exercises server-side constructor pricing, not a fake ID.
        product_id = self.compose(
            "exec",
            "-T",
            "backend",
            "python",
            "-c",
            """
import asyncio
from decimal import Decimal
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import get_settings
from app.db import models
from app.modules.catalog.models import Product
async def seed():
    engine = create_async_engine(get_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            product = Product(title='Container smoke item', price=Decimal('1500'),
                              sizes=['M'], colors=['black'], stock_quantity=10)
            session.add(product)
            await session.commit()
            print(product.id)
    finally:
        await engine.dispose()
asyncio.run(seed())
""",
        )
        if not re.fullmatch(r"[1-9][0-9]*", product_id):
            raise SmokeFailure("Cart fixture was not created")
        # Capability stays in memory and HTTP; never in command arguments or logs.
        path = "/api/cart/" + secrets.token_urlsafe(32)

        def snapshot(base: str, **kwargs) -> dict:
            body, content_type = request(base, path, no_store=True, **kwargs)
            if "application/json" not in content_type:
                raise SmokeFailure("Cart response must be JSON")
            return json.loads(body)

        fresh = snapshot(frontend)
        if fresh.get("items") != [] or fresh.get("revision") is not None:
            raise SmokeFailure("Fresh cart is not empty")
        payload = {
            "expected_revision": None,
            "operation_id": secrets.token_hex(16),
            "items": [
                {
                    "id": "container-smoke-item",
                    "product_id": int(product_id),
                    "title": "Container smoke item",
                    "price": "0.01",
                    "size": "M",
                    "color": "black",
                    "quantity": 2,
                    "customization": {
                        "kind": "constructor",
                        "decorations": [
                            {
                                "uid": "smoke-text",
                                "scale": 1.0,
                                "type": "text",
                                "text": "Smoke",
                            }
                        ],
                    },
                }
            ],
        }
        saved = snapshot(frontend, method="PUT", payload=payload)
        items = saved.get("items", [])
        if (
            not re.fullmatch(r"[a-f0-9]{32}", saved.get("revision") or "")
            or len(items) != 1
            or items[0].get("product_id") != int(product_id)
            or items[0].get("quantity") != 2
            or items[0].get("price") != 1580
            or items[0].get("customization", {}).get("totalPrice") != 1580
        ):
            raise SmokeFailure("Cart did not persist the server-priced constructor item")
        if snapshot(frontend, method="PUT", payload=payload) != saved:
            raise SmokeFailure("Cart operation replay changed the saved snapshot")
        conflict = snapshot(
            frontend,
            method="PUT",
            expected=409,
            payload={**payload, "operation_id": secrets.token_hex(16)},
        )
        if conflict.get("detail", {}).get("code") != "cart_conflict":
            raise SmokeFailure("Cart accepted a stale revision")
        # Stop the API process and Redis together. PostgreSQL remains the durable store.
        self.compose("stop", "--timeout", "20", "backend", "redis")
        # Compose start traverses depends_on and can start Redis again.
        self.compose(
            "up",
            "-d",
            "--no-deps",
            "--no-recreate",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "180",
            "backend",
        )
        if self.compose("ps", "--status", "running", "--services", "redis"):
            raise SmokeFailure("Redis is running during the durable cart check")
        # Docker can allocate another random host port on start, even without recreate.
        previous_backend = backend
        backend = self.endpoint("backend", "8000")
        if frontend == previous_backend:
            frontend = backend
        for base in (backend, frontend):
            if snapshot(base) != saved:
                raise SmokeFailure("Confirmed cart was lost after API restart without Redis")
        print("Cart HTTP passed: server pricing, replay, conflict, API restart, Redis stopped")

    def run(self) -> None:
        try:
            self.compose("config", "--quiet")
            self.compose(
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "180",
                "postgres",
                "redis",
                "minio",
            )
            for job in ("database-role-init", "minio-init", "migrate"):
                self.compose("run", "--rm", "--no-deps", "-T", job)
            self.compose(
                "up",
                "-d",
                "--no-deps",
                "--pull",
                "never",
                "--wait",
                "--wait-timeout",
                "180",
                "backend",
                "frontend",
            )
            for service, command in (
                ("backend", ["python", "-c", "import os; assert os.getuid() == 10001"]),
                (
                    "frontend",
                    ["node", "-e", "if(process.getuid()!==10001)process.exit(1)"],
                ),
            ):
                self.compose("exec", "-T", service, *command)
            self.compose(
                "exec",
                "-T",
                "backend",
                "python",
                "-c",
                """
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings
async def check():
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text('''
                SELECT current_user = 'smoke_app'
                   AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
                   AND NOT rolreplication
                   AND NOT has_schema_privilege(current_user, 'public', 'CREATE')
                FROM pg_roles WHERE rolname = current_user
            '''))
            assert result.scalar_one() is True
    finally:
        await engine.dispose()
asyncio.run(check())
""",
            )
            backend = self.endpoint("backend", "8000")
            frontend = self.endpoint("frontend", "3000")
            verify_http(backend, frontend)
            self.verify_persistent_cart(backend, frontend)
            # Re-running head must be safe for already populated migration metadata.
            self.compose("run", "--rm", "--no-deps", "-T", "migrate")
        finally:
            self.compose("down", "--volumes", "--remove-orphans", "--timeout", "20", timeout=90)
            self.cleaned = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-image", default="garment-buro-backend:ci")
    parser.add_argument("--frontend-image", default="garment-buro-frontend:ci")
    parser.add_argument("--minio-image", default=DEFAULT_MINIO_IMAGE)
    args = parser.parse_args()
    if not shutil.which("docker"):
        print(
            "Container smoke requires Docker Engine and the Compose plugin",
            file=sys.stderr,
        )
        return 1
    temporary = Path(tempfile.mkdtemp(prefix="garment-container-smoke-"))
    smoke = None

    def interrupted(signum, _frame):
        raise SmokeFailure(f"Interrupted by signal {signum}")

    previous_handlers = {
        number: signal.signal(number, interrupted) for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        smoke = ContainerSmoke(
            temporary, args.backend_image, args.frontend_image, minio_image=args.minio_image
        )
        smoke.run()
    except (SmokeFailure, OSError, subprocess.TimeoutExpired, ValueError) as error:
        # Exceptions from transports may embed command arguments or response data.
        detail = str(error) if isinstance(error, SmokeFailure) else type(error).__name__
        print(f"Container smoke failed: {detail}", file=sys.stderr)
        return 1
    finally:
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)
        if smoke is None or smoke.cleaned:
            shutil.rmtree(temporary)
        else:
            print(
                f"Cleanup incomplete for {smoke.project}; private config retained at {temporary}",
                file=sys.stderr,
            )
    print("Container smoke passed; disposable project and volumes removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
