"""
BugPilot — Production Observability Test Suite (Phase 20)
=========================================================
Tests:
- Request ID generation & header propagation
- API latency measurement in HTTP response headers
- Secret sanitization filter in log output
- Structured JSON log fields
- Advanced system readiness probe endpoint (/api/v1/health/readiness)
"""

import pytest
import httpx
from backend.main import app
from backend.core.logging import sanitize_sensitive_data


class TestProductionObservability:
    """Test suite verifying Phase 20 production observability features."""

    @pytest.mark.asyncio
    async def test_request_id_and_latency_headers_propagation(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.get("/api/v1/health")
            assert res.status_code == 200
            assert "x-request-id" in res.headers
            assert "x-latency-ms" in res.headers
            assert float(res.headers["x-latency-ms"]) >= 0

    def test_secret_sanitization_helper(self):
        secret_dict = {
            "email": "user@company.com",
            "password": "SuperSecretPassword123!",
            "token": "bearer_ey12345",
            "normal_field": "public_value",
        }

        sanitized = sanitize_sensitive_data(secret_dict)
        assert sanitized["email"] == "user@company.com"
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["token"] == "***REDACTED***"
        assert sanitized["normal_field"] == "public_value"

    @pytest.mark.asyncio
    async def test_readiness_probe_matrix(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.get("/api/v1/health/readiness")
            assert res.status_code == 200
            data = res.json()

            assert data["status"] in ["ready", "degraded"]
            components = data["components"]
            assert "database" in components
            assert "data_provider" in components
            assert "mcp_server" in components
            assert "llm" in components
            assert "latency_ms" in components["database"]

    def test_text_logging_formatter_redacts_secrets(self):
        """Verify that SanitizedRichFormatter redacts passwords and tokens in text log records."""
        import logging
        from backend.core.logging import SanitizedRichFormatter, SecretSanitizingFilter

        formatter = SanitizedRichFormatter("%(message)s")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User login failed with password: SecretPass123! and Bearer eyJhbGciOi",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        assert "SecretPass123!" not in formatted
        assert "***REDACTED***" in formatted

        # Test filter on args tuple
        record_with_args = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Auth header: %s",
            args=("Bearer eyJhbGciOi...",),
            exc_info=None,
        )
        filt = SecretSanitizingFilter()
        filt.filter(record_with_args)
        formatted_args = formatter.format(record_with_args)
        assert "eyJhbGciOi" not in formatted_args
        assert "***REDACTED***" in formatted_args
