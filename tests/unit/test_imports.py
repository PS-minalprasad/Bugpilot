"""
Phase 1 Test — Project Imports
================================
Verifies that all foundation packages and modules import without error.

Acceptance criterion AC-01: project imports successfully.
"""

import pytest


class TestCoreImports:
    """Core module import checks."""

    def test_backend_package_imports(self):
        import backend
        assert backend is not None

    def test_config_imports(self):
        from backend.config import Settings, settings, get_settings
        assert Settings is not None
        assert settings is not None
        assert get_settings is not None

    def test_core_logging_imports(self):
        from backend.core.logging import setup_logging, get_logger, logger
        assert setup_logging is not None
        assert get_logger is not None
        assert logger is not None

    def test_core_exceptions_imports(self):
        from backend.core.exceptions import (
            BugPilotError,
            ConfigurationError,
            DataProviderError,
            BugNotFoundError,
            MCPError,
            AgentError,
            LLMError,
            ValidationError,
        )
        assert BugPilotError is not None
        assert ConfigurationError is not None

    def test_core_observability_imports(self):
        from backend.core.observability import new_request_id, timed
        assert new_request_id is not None
        assert timed is not None

    def test_models_package_imports(self):
        import models
        assert models is not None

    def test_bug_model_imports(self):
        from models.bug import Bug, BugSeverity, BugStatus, BugPriority
        assert Bug is not None
        assert BugSeverity is not None

    def test_sprint_model_imports(self):
        from models.sprint import Sprint, SprintStatus
        assert Sprint is not None
        assert SprintStatus is not None

    def test_analysis_model_imports(self):
        from models.analysis import AnalysisRequest, AnalysisStatus, AnalysisScope
        assert AnalysisRequest is not None
        assert AnalysisStatus is not None

    def test_report_model_imports(self):
        from models.report import AnalysisReport, ReflectionResult, ReportSection
        assert AnalysisReport is not None
        assert ReflectionResult is not None

    def test_placeholder_packages_import(self):
        """Placeholder packages must import without error."""
        import agents
        import analytics
        import mcp_server
        import mcp_client
        import providers
        import data
        assert agents is not None
        assert analytics is not None

    def test_fastapi_app_imports(self):
        from backend.main import app, create_app
        assert app is not None
        assert create_app is not None

    def test_health_router_imports(self):
        from backend.api.routes.health import router, health, readiness
        assert router is not None
