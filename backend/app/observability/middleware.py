from __future__ import annotations

import asyncio
import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.routing import RouteContext, iter_route_contexts
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.logging import request_id_context

logger = logging.getLogger("app.http")
SAFE_REQUEST_ID = re.compile(rb"[A-Za-z0-9_-]{1,128}")


class RequestObservabilityMiddleware:
    """Observe ASGI without reading request bodies or buffering streamed responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._route_contexts: dict[int, list[RouteContext]] = {}

    def _route_template(self, scope: Scope) -> str:
        route = scope.get("route")
        if route is None:
            return "<unmatched>"
        path = scope["path"]
        root = scope.get("root_path", "")
        if root and (path == root or path.startswith(root + "/")):
            path = path[len(root) :] or "/"

        def selected_template() -> str | None:
            for context in self._route_contexts.get(id(route), ()):
                if context.path is not None and context.path_regex.match(path):
                    return context.path
            return None

        template = selected_template()
        if template is None:
            # FastAPI preserves routers instead of cloning their routes. Resolve
            # configured inclusion prefixes once, including repeated inclusion
            # of a shared router. Never construct a log value from a request URL.
            index: dict[int, list[RouteContext]] = {}
            for context in iter_route_contexts(getattr(scope.get("app"), "routes", ())):
                index.setdefault(id(context.original_route), []).append(context)
            self._route_contexts.update(index)
            template = selected_template()
        return template or getattr(route, "path", "<unmatched>")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = [value for key, value in scope["headers"] if key.lower() == b"x-request-id"]
        request_id = (
            supplied[0].decode("ascii")
            if len(supplied) == 1 and SAFE_REQUEST_ID.fullmatch(supplied[0])
            else uuid4().hex
        )
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        started_at = perf_counter()
        status_code = 500
        error_type = None

        async def observed_send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, observed_send)
        except asyncio.CancelledError:
            error_type = "CancelledError"
            raise
        except Exception as error:
            error_type = type(error).__name__
            raise
        finally:
            try:
                route = self._route_template(scope)
                logger.log(
                    logging.ERROR if error_type or status_code >= 500 else logging.INFO,
                    "HTTP request completed",
                    extra={
                        "event": "http.request.completed",
                        "request_id": request_id,
                        "method": scope["method"],
                        "route": route,
                        "status_code": status_code,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                        "error_type": error_type,
                    },
                )
            finally:
                request_id_context.reset(token)


async def unhandled_error_response(request: Request, _: Exception) -> JSONResponse:
    """ServerErrorMiddleware runs outside user middleware, including on failures."""
    request_id = getattr(request.state, "request_id", None) or uuid4().hex
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )
