from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.factory import create_app


@pytest.fixture(autouse=True)
def context_filter(caplog):
    from app.observability.logging import RequestContextFilter

    capture_filter = RequestContextFilter()
    caplog.handler.addFilter(capture_filter)
    yield
    caplog.handler.removeFilter(capture_filter)


def _app():
    return create_app(settings=Settings(_env_file=None, app_env="test"))


def _requests(caplog):
    return [record for record in caplog.records if record.name == "app.http"]


def test_access_event_uses_route_template_and_omits_customer_input(caplog):
    app = _app()

    @app.post("/api/probe/{customer}")
    async def probe(customer: str):
        logging.getLogger("app.probe").info("inside request")
        return {"ok": True}

    with caplog.at_level(logging.INFO), TestClient(app) as client:
        response = client.post(
            "/api/probe/private-customer?token=query-secret",
            json={"password": "body-secret"},
            headers={
                "X-Request-ID": "browser-request-42",
                "Authorization": "Bearer header-secret",
                "Cookie": "refresh=cookie-secret",
            },
        )

    assert response.headers.get("X-Request-ID") == "browser-request-42"
    events = _requests(caplog)
    assert len(events) == 1
    record = events[0]
    assert record.request_id == "browser-request-42"
    assert record.route == "/api/probe/{customer}"
    assert record.method == "POST"
    assert record.status_code == 200
    assert record.duration_ms >= 0
    from app.observability.logging import JsonFormatter

    output = JsonFormatter().format(record)
    for secret in (
        "private-customer",
        "query-secret",
        "body-secret",
        "header-secret",
        "cookie-secret",
    ):
        assert secret not in output
    payload = json.loads(output)
    assert payload["event"] == "http.request.completed"
    assert payload["timestamp"].endswith("+00:00")
    inside = next(record for record in caplog.records if record.name == "app.probe")
    assert json.loads(JsonFormatter().format(inside))["request_id"] == "browser-request-42"


def test_included_router_uses_full_template_for_each_prefix(caplog):
    app = _app()
    router = APIRouter(prefix="/items")

    @router.get("/{item_id}")
    async def item(item_id: str):
        return {"ok": True}

    # A shared router can be included more than once; its original path alone
    # no longer describes the effective route in modern FastAPI.
    app.include_router(router, prefix="/api/first")
    app.include_router(router, prefix="/api/second")
    with caplog.at_level(logging.INFO), TestClient(app) as client:
        assert client.get("/api/first/items/private-first?token=secret").status_code == 200
        assert client.get("/api/second/items/private-second?token=secret").status_code == 200
        assert client.post("/api/second/items/private-third").status_code == 405
    assert [record.route for record in _requests(caplog)] == [
        "/api/first/items/{item_id}",
        "/api/second/items/{item_id}",
        "/api/second/items/{item_id}",
    ]


@pytest.mark.parametrize("supplied", [None, "x" * 129, "email@example.test", "with spaces"])
def test_invalid_correlation_ids_are_replaced_not_echoed(supplied):
    with TestClient(_app()) as client:
        response = client.get(
            "/health/live", headers={"X-Request-ID": supplied} if supplied else {}
        )
    request_id = response.headers.get("X-Request-ID", "")
    assert len(request_id) == 32
    assert all(char in "0123456789abcdef" for char in request_id)
    assert request_id != supplied


def test_errors_and_unmatched_urls_have_safe_correlation(caplog):
    app = _app()

    @app.get("/api/fail")
    async def fail():
        raise RuntimeError("private exception details")

    @app.get("/api/denied")
    async def denied():
        raise HTTPException(status_code=403, detail="Denied")

    with caplog.at_level(logging.INFO), TestClient(app, raise_server_exceptions=False) as client:
        failed = client.get("/api/fail", headers={"X-Request-ID": "failure-1"})
        denied_response = client.get("/api/denied")
        missing = client.get("/unknown-private-value?token=secret")
    assert failed.status_code == 500
    assert failed.headers.get("X-Request-ID") == "failure-1"
    assert failed.json()["request_id"] == "failure-1"
    assert "private exception details" not in failed.text
    assert denied_response.status_code == 403 and denied_response.headers.get("X-Request-ID")
    assert missing.status_code == 404
    events = _requests(caplog)
    assert [event.status_code for event in events] == [500, 403, 404]
    assert events[0].error_type == "RuntimeError"
    assert events[0].levelno == logging.ERROR
    assert events[2].route == "<unmatched>"
    assert "private exception details" not in events[0].getMessage()


def test_streaming_and_context_ids_remain_isolated(caplog):
    app = _app()

    @app.get("/api/stream/{value}")
    async def stream(value: str):
        async def chunks():
            await asyncio.sleep(0)
            logging.getLogger("app.stream").info("streaming chunk")
            yield value.encode()
            await asyncio.sleep(0)
            yield b"-done"

        return StreamingResponse(chunks())

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await asyncio.gather(
                *(
                    client.get(f"/api/stream/{i}", headers={"X-Request-ID": f"parallel-{i}"})
                    for i in range(4)
                )
            )

    with caplog.at_level(logging.INFO):
        responses = asyncio.run(run())
    assert [response.text for response in responses] == ["0-done", "1-done", "2-done", "3-done"]
    assert [response.headers.get("X-Request-ID") for response in responses] == [
        "parallel-0",
        "parallel-1",
        "parallel-2",
        "parallel-3",
    ]
    from app.observability.logging import JsonFormatter, request_id_context

    streamed = [record for record in caplog.records if record.name == "app.stream"]
    assert {json.loads(JsonFormatter().format(record))["request_id"] for record in streamed} == {
        "parallel-0",
        "parallel-1",
        "parallel-2",
        "parallel-3",
    }
    assert request_id_context.get() is None


def test_formatter_keeps_diagnostic_frames_without_exception_payload():
    from app.observability.logging import JsonFormatter

    try:
        raise ValueError("Bearer top-secret customer@example.test")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "app.runtime", logging.ERROR, __file__, 1, "resource failed", (), sys.exc_info()
        )
    record.authorization = "Bearer hidden-extra"
    formatted = JsonFormatter().format(record)
    payload = json.loads(formatted)
    assert payload["error_type"] == "ValueError"
    assert (
        payload["frames"][-1]["function"]
        == "test_formatter_keeps_diagnostic_frames_without_exception_payload"
    )
    assert all(
        secret not in formatted
        for secret in ("top-secret", "customer@example.test", "hidden-extra")
    )


def test_logging_settings_reject_unsupported_levels():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="VERBOSE")


def test_asgi_observer_forwards_stream_chunks_without_buffering():
    from app.observability.middleware import RequestObservabilityMiddleware

    forwarded = []

    async def stream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"first", "more_body": True})
        assert forwarded[-1]["body"] == b"first"
        await send({"type": "http.response.body", "body": b"last", "more_body": False})

    async def send(message):
        forwarded.append(message)

    async def receive():
        return {"type": "http.disconnect"}

    asyncio.run(
        RequestObservabilityMiddleware(stream)(
            {"type": "http", "headers": [], "method": "GET", "path": "/stream"},
            receive,
            send,
        )
    )
    assert [message.get("body") for message in forwarded[1:]] == [b"first", b"last"]


def test_process_logging_emits_json_and_suppresses_raw_access_urls():
    import subprocess
    import sys

    code = """
import logging
from app.core.config import Settings
from app.observability.logging import configure_logging, request_id_context
configure_logging(Settings(_env_file=None, app_env="test", log_level="WARNING"))
request_id_context.set("worker-test")
logging.getLogger("worker").info("filtered")
logging.getLogger("worker").warning("durable job retained")
logging.getLogger("uvicorn.access").warning("GET /private?token=secret")
logging.getLogger("uvicorn.error").warning("server stopped")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert [row["message"] for row in rows] == ["durable job retained", "server stopped"]
    assert all(row["request_id"] == "worker-test" for row in rows)
    assert not result.stderr
