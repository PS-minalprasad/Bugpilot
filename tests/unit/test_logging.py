"""
Phase 1 Test — Logging Foundation
===================================
Verifies that logging initialises, produces output, and
that get_logger() returns usable logger instances.

Acceptance criterion AC-03: logging initializes.
"""

from __future__ import annotations

import logging
import pytest

from backend.core.logging import setup_logging, get_logger


class TestLoggingSetup:
    """Logging setup and configuration."""

    def test_setup_logging_does_not_raise(self):
        setup_logging(level="DEBUG", fmt="text")

    def test_setup_logging_json_does_not_raise(self):
        # Reset flag to allow re-configuration in test
        import backend.core.logging as log_module
        log_module._configured = False
        setup_logging(level="INFO", fmt="json")
        # Reset again for remaining tests
        log_module._configured = False
        setup_logging(level="DEBUG", fmt="text")

    def test_setup_logging_idempotent(self):
        """Calling setup_logging twice must not raise."""
        setup_logging(level="INFO", fmt="text")
        setup_logging(level="DEBUG", fmt="text")  # second call — no-op

    def test_get_logger_returns_logger(self):
        lg = get_logger("test.module")
        assert isinstance(lg, logging.Logger)

    def test_get_logger_name(self):
        lg = get_logger("bugpilot.test")
        assert lg.name == "bugpilot.test"

    def test_logger_can_emit_info(self):
        lg = get_logger("bugpilot.test.emit")
        # Should not raise
        lg.info("Test log message from Phase 1 test suite")

    def test_logger_can_emit_debug(self):
        lg = get_logger("bugpilot.test.emit")
        lg.debug("Debug message", extra={"phase": 1})

    def test_logger_can_emit_warning(self):
        lg = get_logger("bugpilot.test.emit")
        lg.warning("Warning message")

    def test_logger_can_emit_error(self):
        lg = get_logger("bugpilot.test.emit")
        lg.error("Error message")

    def test_multiple_loggers_are_independent(self):
        lg1 = get_logger("bugpilot.module_a")
        lg2 = get_logger("bugpilot.module_b")
        assert lg1 is not lg2
        assert lg1.name != lg2.name
