from __future__ import annotations

import json
import logging
import logging.config
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone

from app.core.config import Settings

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)

# Explicit fields prevent arbitrary request payloads/extras leaking into access logs.
EVENT_FIELDS = (
    "event",
    "request_id",
    "method",
    "route",
    "status_code",
    "duration_ms",
    "error_type",
    "component",
    "cleanup_counts",
    "dry_run",
)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_context.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON event per line; exception frames omit messages, source and locals."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EVENT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
            payload["frames"] = [
                {"file": frame.filename, "line": frame.lineno, "function": frame.name}
                for frame in traceback.extract_tb(record.exc_info[2])
            ]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(settings: Settings) -> None:
    """Configure once at each executable entrypoint, never inside create_app()."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"request_context": {"()": RequestContextFilter}},
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "discard": {"class": "logging.NullHandler"},
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                    "filters": ["request_context"],
                },
            },
            "root": {"handlers": ["stdout"], "level": settings.log_level},
            "loggers": {
                "uvicorn": {"handlers": [], "propagate": True},
                "uvicorn.error": {"handlers": [], "propagate": True},
                # Our access event uses route templates, unlike Uvicorn's raw URLs.
                "uvicorn.access": {"handlers": ["discard"], "propagate": False},
                "httpx": {"handlers": [], "level": "WARNING", "propagate": True},
                "httpcore": {"handlers": [], "level": "WARNING", "propagate": True},
            },
        }
    )
