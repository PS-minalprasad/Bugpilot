"""
BugPilot — Observability Utilities
=====================================
Request context, correlation IDs, and execution timing.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Generator

from backend.core.logging import get_logger

logger = get_logger("bugpilot.observability")


def new_request_id() -> str:
    """Generate a unique request correlation ID."""
    return str(uuid.uuid4())


@contextmanager
def timed(operation: str, log: bool = True) -> Generator[dict, None, None]:
    """
    Context manager that measures wall-clock execution time.

    Usage::

        with timed("my_operation") as t:
            do_work()
        print(t["elapsed_ms"])

    Args:
        operation: Human-readable label for the timed block.
        log:       Whether to emit a log line on exit.

    Yields:
        A dict that will be populated with ``elapsed_ms`` on exit.
    """
    result: dict = {"operation": operation, "elapsed_ms": 0.0}
    start = time.perf_counter()
    try:
        yield result
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        result["elapsed_ms"] = round(elapsed, 2)
        if log:
            logger.debug(
                "Operation completed",
                extra={"operation": operation, "elapsed_ms": result["elapsed_ms"]},
            )
