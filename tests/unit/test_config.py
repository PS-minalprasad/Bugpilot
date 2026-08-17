"""
Phase 1 Test — Configuration
==============================
Verifies that Settings load correctly, validators fire,
and no secrets are exposed.

Acceptance criterion AC-02: configuration loads.
"""

from __future__ import annotations

import os
import pytest

from backend.config import Settings, settings, get_settings


class TestSettingsDefaults:
    """Settings load with expected defaults."""

    def test_settings_singleton(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2, "get_settings() must return the same singleton"

    def test_app_name(self):
        assert settings.APP_NAME == "BugPilot"

    def test_app_version_format(self):
        parts = settings.APP_VERSION.split(".")
        assert len(parts) == 3, "version must be semantic (x.y.z)"

    def test_default_env_is_test(self):
        """conftest forces ENV=test."""
        assert settings.ENV == "test"

    def test_api_prefix(self):
        assert settings.API_PREFIX.startswith("/")

    def test_cors_origins_is_list(self):
        assert isinstance(settings.CORS_ORIGINS, list)
        assert len(settings.CORS_ORIGINS) > 0

    def test_log_level_uppercased(self):
        assert settings.LOG_LEVEL == settings.LOG_LEVEL.upper()

    def test_data_label(self):
        assert settings.DATA_LABEL in ["SQLite", "PostgreSQL"]
        assert settings.data_label in ["SQLite", "PostgreSQL"]

    def test_port_is_int(self):
        assert isinstance(settings.PORT, int)
        assert 1024 <= settings.PORT <= 65535

    def test_mcp_server_port_is_int(self):
        assert isinstance(settings.MCP_SERVER_PORT, int)


class TestSettingsHelpers:
    """Helper properties on Settings."""

    def test_is_development_false_in_test(self):
        # ENV=test, so is_development should be False
        assert not settings.is_development

    def test_is_production_false_in_test(self):
        assert not settings.is_production

    def test_openapi_url_available_in_non_production(self):
        # test env is not production, so openapi_url should not be None
        assert settings.openapi_url is not None


class TestSettingsValidation:
    """Validators reject invalid values."""

    def test_invalid_env_raises(self):
        with pytest.raises(Exception):
            Settings(ENV="invalid_env", _env_file=None)

    def test_invalid_log_level_raises(self):
        with pytest.raises(Exception):
            Settings(LOG_LEVEL="VERBOSE", _env_file=None)


class TestNoHardcodedSecrets:
    """Ensure no secrets are hardcoded in config defaults."""

    def test_gemini_api_key_default_is_empty(self):
        s = Settings(_env_file=None)
        assert s.GEMINI_API_KEY == "", (
            "GEMINI_API_KEY must default to empty string — never hardcode a key"
        )
