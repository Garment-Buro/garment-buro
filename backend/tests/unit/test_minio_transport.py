from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from time import monotonic
from urllib.parse import urlsplit

import pytest
from minio import Minio
from minio.error import S3Error
from pydantic import ValidationError
from urllib3 import PoolManager
from urllib3.exceptions import HTTPError

from app.core.config import AppEnvironment, Settings
from app.integrations.minio import MinioStorage
from tests.fakes.minio import FakeMinioClient


class StorageServer(ThreadingHTTPServer):
    """Real HTTP faults; never uses an external service or real credentials."""

    def __init__(self, fault: str) -> None:
        super().__init__(("127.0.0.1", 0), StorageHandler)
        self.fault = fault
        self.calls: Counter[str] = Counter()
        self.release = Event()


class StorageHandler(BaseHTTPRequestHandler):
    server: StorageServer

    def log_message(self, *_args: object) -> None:
        pass

    def respond(self, status: int, body: bytes = b"", **headers: str) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", "application/xml")
        for name, value in headers.items():
            self.send_header(name.replace("_", "-"), value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def dispatch(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.query == "location=":
            self.respond(200, b"<LocationConstraint>us-east-1</LocationConstraint>")
            return
        if parsed.query == "policy=":
            self.respond(404, b"<Error><Code>NoSuchBucketPolicy</Code></Error>")
            return
        if self.command == "PUT":
            self.rfile.read(int(self.headers["Content-Length"]))
        self.server.calls[self.command] += 1
        count = self.server.calls[self.command]
        fault = self.server.fault
        if fault == "once503-slow":
            # A healthy local server need not answer within 50ms under load.
            self.server.release.wait(0.1)
        if fault == "proxy-error":
            body = b"<html>private proxy diagnostics</html>"
            self.send_response(503)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if fault == "redirect":
            self.respond(307, Location=f"http://127.0.0.1:{self.server.server_port}{self.path}")
            return
        if fault == "headers":
            self.server.release.wait(2.0)
        if fault == "always503" or (
            fault in {"once503", "once503-slow", "retry-after"} and count == 1
        ):
            headers = {"Retry_After": "60"} if fault == "retry-after" else {}
            self.respond(503, b"<Error><Code>SlowDown</Code></Error>", **headers)
            return
        if self.command == "GET":
            if fault == "body":
                self.send_response(200)
                self.send_header("Content-Length", "4")
                self.end_headers()
                self.wfile.write(b"d")
                self.wfile.flush()
                self.server.release.wait(2.0)
                self.wfile.write(b"ata")
            else:
                self.respond(200, b"data")
        else:
            self.respond(204 if self.command == "DELETE" else 200, ETag='"test-etag"')

    def handle_request(self) -> None:
        try:
            self.dispatch()
        except (BrokenPipeError, ConnectionResetError):
            # Expected when a bounded client gives up before the server responds.
            pass

    do_GET = do_HEAD = do_PUT = do_DELETE = handle_request


@contextmanager
def storage_server(fault: str) -> Iterator[StorageServer]:
    server = StorageServer(fault)
    thread = Thread(target=lambda: server.serve_forever(poll_interval=0.01))
    thread.start()
    try:
        yield server
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def settings(server: StorageServer, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": AppEnvironment.TEST,
        "minio_enabled": True,
        "minio_endpoint": f"127.0.0.1:{server.server_port}",
        "minio_access_key": "test-access",
        "minio_secret_key": "test-secret",
        "minio_public_base_url": f"http://127.0.0.1:{server.server_port}",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def operation(storage: MinioStorage, method: str) -> object:
    if method == "HEAD":
        return await asyncio.to_thread(
            storage.client.bucket_exists, storage.settings.minio_customer_projects_bucket
        )
    if method == "GET":
        return await storage.read_private_customer_object("project/file", max_bytes=4)
    if method == "PUT":
        return await storage.put_private_customer_object(
            object_key="project/file", data=b"data", content_type="application/octet-stream"
        )
    assert method == "DELETE"
    return await storage.remove_private_crm_object("crm/file")


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize("fault", ["once503", "once503-slow"])
def test_transient_read_failure_is_retried_once(method: str, fault: str) -> None:
    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(settings(server))
        await storage.startup()
        try:
            result = await operation(storage, method)
            assert result == (b"data" if method == "GET" else True)
            assert server.calls[method] == 2
        finally:
            await storage.shutdown()

    with storage_server(fault) as server:
        asyncio.run(scenario(server))


@pytest.mark.parametrize("method", ["GET", "HEAD", "PUT", "DELETE"])
def test_failed_operations_have_bounded_attempts(method: str, monkeypatch) -> None:
    monkeypatch.setattr("urllib3.util.retry.time.sleep", lambda _seconds: None)

    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(settings(server))
        await storage.startup()
        try:
            with pytest.raises((HTTPError, S3Error)):
                await operation(storage, method)
            # Repeating PUT/DELETE can create duplicate versions/delete markers.
            assert server.calls[method] == (2 if method in {"GET", "HEAD"} else 1)
        finally:
            await storage.shutdown()

    with storage_server("always503") as server:
        asyncio.run(scenario(server))


@pytest.mark.parametrize("method", ["HEAD", "PUT", "DELETE"])
def test_stalled_headers_timeout_without_repeating_ambiguous_writes(method: str) -> None:
    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(
            settings(server, minio_connect_timeout_seconds=0.2, minio_read_timeout_seconds=0.2)
        )
        await storage.startup()
        try:
            started = monotonic()
            with pytest.raises(HTTPError):
                await operation(storage, method)
            assert monotonic() - started < 1.5
            assert server.calls[method] == (2 if method == "HEAD" else 1)
        finally:
            await storage.shutdown()

    with storage_server("headers") as server:
        asyncio.run(scenario(server))


def test_stalled_private_body_times_out() -> None:
    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(
            settings(server, minio_connect_timeout_seconds=0.2, minio_read_timeout_seconds=0.2)
        )
        await storage.startup()
        try:
            started = monotonic()
            with pytest.raises(HTTPError):
                await operation(storage, "GET")
            assert monotonic() - started < 1.5
            assert server.calls["GET"] == 1
        finally:
            await storage.shutdown()

    with storage_server("body") as server:
        asyncio.run(scenario(server))


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_proxy_error_uses_the_existing_unavailable_boundary(method: str) -> None:
    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(settings(server))
        await storage.startup()
        try:
            with pytest.raises(HTTPError) as raised:
                await operation(storage, method)
            assert "private proxy diagnostics" not in str(raised.value)
            assert server.calls[method] == 1
        finally:
            await storage.shutdown()

    with storage_server("proxy-error") as server:
        asyncio.run(scenario(server))


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_redirect_cannot_repeat_a_write(method: str) -> None:
    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(settings(server))
        await storage.startup()
        try:
            with pytest.raises(HTTPError):
                await operation(storage, method)
            assert server.calls[method] == 1
        finally:
            await storage.shutdown()

    with storage_server("redirect") as server:
        asyncio.run(scenario(server))


def test_retry_after_cannot_impose_long_waits(monkeypatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr("urllib3.util.retry.time.sleep", waits.append)

    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(settings(server))
        await storage.startup()
        try:
            assert await operation(storage, "GET") == b"data"
            assert server.calls["GET"] == 2
            assert not waits
        finally:
            await storage.shutdown()

    with storage_server("retry-after") as server:
        asyncio.run(scenario(server))


@pytest.mark.parametrize("fault,ready", [("healthy", True), ("headers", False)])
def test_readiness_uses_the_same_bounded_transport(fault: str, ready: bool) -> None:
    async def scenario(server: StorageServer) -> None:
        overrides = (
            {"minio_connect_timeout_seconds": 0.2, "minio_read_timeout_seconds": 0.2}
            if fault == "headers"
            else {}
        )
        storage = MinioStorage(settings(server, **overrides))
        await storage.startup()
        try:
            assert await storage.ping() is ready
        finally:
            await storage.shutdown()

    with storage_server(fault) as server:
        asyncio.run(scenario(server))


def test_owned_pool_is_cleared_and_storage_can_restart(monkeypatch) -> None:
    pools: list[PoolManager] = []

    def create_client(**kwargs):
        pools.append(kwargs["http_client"])
        return Minio(**kwargs)

    monkeypatch.setattr("app.integrations.minio.Minio", create_client)

    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(settings(server))
        for _ in range(2):
            await storage.startup()
            await storage.startup()
            assert await operation(storage, "GET") == b"data"
            assert len(pools[-1].pools) == 1
            await storage.shutdown()
            assert len(pools[-1].pools) == 0
            await storage.shutdown()
        assert len(pools) == 2
        assert pools[0] is not pools[1]

    with storage_server("healthy") as server:
        asyncio.run(scenario(server))


def test_failed_startup_releases_pool_and_can_retry(monkeypatch) -> None:
    cleared: list[PoolManager] = []

    class TrackedPool(PoolManager):
        def clear(self):
            cleared.append(self)
            super().clear()

    def invalid_client(**_kwargs):
        raise ValueError("synthetic construction failure")

    monkeypatch.setattr("app.integrations.minio.PoolManager", TrackedPool)
    monkeypatch.setattr("app.integrations.minio.Minio", invalid_client)

    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(settings(server))
        with pytest.raises(ValueError, match="synthetic construction failure"):
            await storage.startup()
        assert len(cleared) == 1
        monkeypatch.setattr("app.integrations.minio.Minio", Minio)
        await storage.startup()
        try:
            assert await operation(storage, "GET") == b"data"
        finally:
            await storage.shutdown()

    with storage_server("healthy") as server:
        asyncio.run(scenario(server))


def test_injected_client_does_not_allocate_or_clear_an_owned_pool(monkeypatch) -> None:
    def unexpected_pool(**_kwargs):
        pytest.fail("injected client must not allocate a transport")

    monkeypatch.setattr("app.integrations.minio.PoolManager", unexpected_pool)

    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(settings(server), client=FakeMinioClient())
        await storage.startup()
        assert await storage.ping()
        await storage.shutdown()

    with storage_server("healthy") as server:
        asyncio.run(scenario(server))


@pytest.mark.parametrize("custom_ca", [False, True])
def test_transport_preserves_certificate_verification_and_custom_ca(custom_ca, monkeypatch):
    import certifi

    pools: list[PoolManager] = []

    def create_client(**kwargs):
        pools.append(kwargs["http_client"])
        return Minio(**kwargs)

    monkeypatch.setattr("app.integrations.minio.Minio", create_client)
    if custom_ca:
        monkeypatch.setenv("SSL_CERT_FILE", "/synthetic/company-ca.pem")
    else:
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)

    async def scenario(server: StorageServer) -> None:
        storage = MinioStorage(settings(server, minio_secure=True))
        await storage.startup()
        try:
            pool = pools[0].connection_from_url("https://storage.test")
            assert pool.cert_reqs == "CERT_REQUIRED"
            assert pool.ca_certs == ("/synthetic/company-ca.pem" if custom_ca else certifi.where())
        finally:
            await storage.shutdown()

    with storage_server("healthy") as server:
        asyncio.run(scenario(server))


@pytest.mark.parametrize(
    "field,maximum",
    [
        ("minio_connect_timeout_seconds", 30),
        ("minio_read_timeout_seconds", 60),
    ],
)
@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), "above-maximum"])
def test_transport_timeouts_must_be_finite_positive_and_bounded(field, maximum, value) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(_env_file=None, **{field: maximum + 1 if value == "above-maximum" else value})
