"""
BugPilot — Logging Foundation
==============================
Configures structured logging for the application.
Supports both human-readable (text) and JSON output formats.

Usage:
    from backend.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Something happened", key="value")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

_console = Console(stderr=True)
_configured = False


def setup_logging(level: str = "INFO", fmt: str = "text") -> None:
    """
    Configure root logger once.

    Args:
        level: One of DEBUG / INFO / WARNING / ERROR / CRITICAL.
        fmt:   "text" for rich human-readable, "json" for structured output.
    """
    global _configured
    if _configured:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    if fmt == "json":
        _setup_json_logging(numeric_level)
    else:
        _setup_rich_logging(numeric_level)

    _configured = True


def _setup_rich_logging(level: int) -> None:
    """Human-readable coloured logging via Rich."""
    handler = RichHandler(
        console=_console,
        show_time=True,
        show_level=True,
        show_path=True,
        markup=True,
        rich_tracebacks=True,
        log_time_format="[%H:%M:%S]",
    )
    handler.setLevel(level)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%H:%M:%S]",
        handlers=[handler],
        force=True,
    )

    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def sanitize_sensitive_data(value: Any) -> Any:
    """Recursively redacts passwords, tokens, keys, and authorization secrets."""
    if isinstance(value, str):
        lower_val = value.lower()
        if any(secret in lower_val for secret in ["bearer ", "password", "token", "secret", "authorization"]):
            return "***REDACTED***"
        return value
    if isinstance(value, dict):
        sanitized = {}
        for k, v in value.items():
            if any(secret in k.lower() for secret in ["password", "token", "secret", "authorization", "key"]):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = sanitize_sensitive_data(v)
        return sanitized
    if isinstance(value, list):
        return [sanitize_sensitive_data(item) for item in value]
    return value


def _setup_json_logging(level: int) -> None:
    """Simple JSON-structured logging for production/CI."""
    import json
    import datetime

    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload: dict[str, Any] = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": sanitize_sensitive_data(record.getMessage()),
            }
            if record.exc_info:
                payload["exception"] = self.formatException(record.exc_info)
            # Attach any extra fields
            for key, val in record.__dict__.items():
                if key not in {
                    "name", "msg", "args", "levelname", "levelno", "pathname",
                    "filename", "module", "exc_info", "exc_text", "stack_info",
                    "lineno", "funcName", "created", "msecs", "relativeCreated",
                    "thread", "threadName", "processName", "process", "message",
                    "taskName",
                }:
                    payload[key] = sanitize_sensitive_data(val)
            return json.dumps(payload)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Call setup_logging() first (done automatically by the app on startup).

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        Standard Python Logger instance.
    """
    return logging.getLogger(name)


# Module-level convenience logger for core internals.
logger = get_logger("bugpilot.core")
