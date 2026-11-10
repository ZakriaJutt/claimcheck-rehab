"""Structured JSON logging with a correlation ID (R-07, R-12).

No web-framework import here: the worker uses this module. Log IDs and counts only; never an
invoice reference, claim token, amount or date of service.
"""

from __future__ import annotations

import contextvars
import json
import logging as _std
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)

# Keys that must never appear in a log record's extra fields.
FORBIDDEN_KEYS = frozenset(
    {"invoice_ref", "claim_token", "amount", "amount_invoiced", "amount_paid", "date_of_service", "payload"}
)


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def set_correlation_id(value: str | None) -> contextvars.Token[str | None]:
    return _correlation_id.set(value)


def reset_correlation_id(token: contextvars.Token[str | None]) -> None:
    _correlation_id.reset(token)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


class JsonFormatter(_std.Formatter):
    def format(self, record: _std.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None) or get_correlation_id(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            for key, value in fields.items():
                if key in FORBIDDEN_KEYS:
                    value = "[withheld]"
                data[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            data["error_type"] = record.exc_info[0].__name__
        return json.dumps(data, default=str)


def configure(level: str = "INFO") -> None:
    root = _std.getLogger("claimcheck")
    root.setLevel(level)
    if not any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        handler = _std.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    root.propagate = False


def get_logger(name: str) -> _std.Logger:
    return _std.getLogger(f"claimcheck.{name}")


def log_event(logger: _std.Logger, event: str, level: int = _std.INFO, **fields: Any) -> None:
    """Log an event with ID and count fields. Forbidden keys are withheld by the formatter."""
    logger.log(level, event, extra={"fields": fields})
