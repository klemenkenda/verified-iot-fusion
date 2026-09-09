"""Structured logging.

Every line is one JSON object on stderr, carrying the run id, so that the log of an
official run can be parsed rather than read. Section 12 requires runs to be traceable;
a log line without its run id cannot be attributed to one.

Logs go to stderr and results to stdout, so a command's output can be piped without the
log stream contaminating it.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

LOGGER_NAME = "vifusion"

# Attributes present on every LogRecord; anything else was supplied by the caller as a
# structured field and is emitted alongside the message.
_STANDARD_FIELDS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render a record as a single canonical JSON line."""

    def __init__(self, run_id: str | None = None) -> None:
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        if self.run_id is not None:
            payload["run_id"] = self.run_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO, run_id: str | None = None) -> logging.Logger:
    """Install the JSON handler on the project logger and return it.

    Replaces any handler installed by an earlier call, so repeated configuration inside one
    process does not duplicate every line.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter(run_id=run_id))
    logger.addHandler(handler)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the project logger, or a named child of it."""
    return logging.getLogger(LOGGER_NAME if name is None else f"{LOGGER_NAME}.{name}")
