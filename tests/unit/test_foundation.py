"""
Phase 1 Test — Application Foundation
=======================================
Verifies that the FastAPI application:
  - starts (lifespan runs)
  - responds on GET /api/health with 200 + expected body
  - responds on GET /api/health/ready with 200
  - handles unknown routes with 404

Acceptance criterion AC-05: application foundation starts.
"""

from __future__ import annotations

import pytest


class TestHealthEndpoint:
    """GET /api/health — liveness check."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        response = await client.get("/api/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_status_is_ok(self, client):
        response = await client.get("/api/health")
        body = response.json()
        assert body["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_app_name(self, client):
        response = await client.get("/api/health")
        body = response.json()
        assert body["app"] == "BugPilot"

    @pytest.mark.asyncio
    async def test_health_data_source(self, client):
        response = await client.get("/api/health")
        body = response.json()
        assert body["data_source"] in ["SQLite", "PostgreSQL"]

    @pytest.mark.asyncio
    async def test_health_version_present(self, client):
        response = await client.get("/api/health")
        body = response.json()
        assert "version" in body
        assert body["version"] != ""

    @pytest.mark.asyncio
    async def test_health_timestamp_present(self, client):
        response = await client.get("/api/health")
        body = response.json()
        assert "timestamp" in body
        # ISO-8601 format ends with Z
        assert body["timestamp"].endswith("Z")

    @pytest.mark.asyncio
    async def test_health_env_present(self, client):
        response = await client.get("/api/health")
        body = response.json()
        assert "env" in body


class TestReadinessEndpoint:
    """GET /api/health/ready — component readiness check."""

    @pytest.mark.asyncio
    async def test_readiness_returns_200(self, client):
        response = await client.get("/api/health/ready")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readiness_status_is_ready(self, client):
        response = await client.get("/api/health/ready")
        body = response.json()
        assert body["status"] == "ready"

    @pytest.mark.asyncio
    async def test_readiness_components_present(self, client):
        response = await client.get("/api/health/ready")
        body = response.json()
        assert "components" in body
        components = body["components"]
        assert "config" in components
        assert "logging" in components

    @pytest.mark.asyncio
    async def test_readiness_config_component_ready(self, client):
        response = await client.get("/api/health/ready")
        body = response.json()
        assert body["components"]["config"]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_readiness_mcp_not_configured(self, client):
        response = await client.get("/api/health/ready")
        body = response.json()
        assert body["components"]["mcp_server"]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_readiness_timestamp_present(self, client):
        response = await client.get("/api/health/ready")
        body = response.json()
        assert "timestamp" in body


class TestUnknownRoutes:
    """Unknown routes return 404."""

    @pytest.mark.asyncio
    async def test_unknown_route_404(self, client):
        response = await client.get("/api/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_root_route_200(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "documentation" in data


class TestExceptions:
    """Exception hierarchy is correct."""

    def test_bugpilot_error_base(self):
        from backend.core.exceptions import BugPilotError
        err = BugPilotError("test error")
        assert err.detail == "test error"
        assert err.http_status == 500
        assert err.error_code == "BUGPILOT_ERROR"

    def test_bug_not_found_http_404(self):
        from backend.core.exceptions import BugNotFoundError
        err = BugNotFoundError("BP-999 not found")
        assert err.http_status == 404
        assert err.error_code == "BUG_NOT_FOUND"

    def test_mcp_error_inherits_bugpilot_error(self):
        from backend.core.exceptions import MCPError, BugPilotError
        err = MCPError("mcp failed")
        assert isinstance(err, BugPilotError)

    def test_agent_error_inherits_bugpilot_error(self):
        from backend.core.exceptions import AgentError, BugPilotError
        err = AgentError("agent failed")
        assert isinstance(err, BugPilotError)


class TestObservability:
    """Observability utilities work correctly."""

    def test_new_request_id_generates_uuid(self):
        from backend.core.observability import new_request_id
        rid = new_request_id()
        assert len(rid) == 36  # UUID4 format
        assert rid.count("-") == 4

    def test_new_request_id_unique(self):
        from backend.core.observability import new_request_id
        ids = {new_request_id() for _ in range(100)}
        assert len(ids) == 100, "Request IDs must be unique"

    def test_timed_context_manager(self):
        import time
        from backend.core.observability import timed

        with timed("test_op", log=False) as t:
            time.sleep(0.01)

        assert t["elapsed_ms"] >= 10.0
        assert t["operation"] == "test_op"
