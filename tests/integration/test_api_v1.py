"""
BugPilot — FastAPI Backend Integration & Unit Test Suite (Phase 9)
===================================================================
Verifies FastAPI endpoints:
  - GET  /api/v1/health
  - GET  /api/v1/agents
  - GET  /api/v1/tools
  - POST /api/v1/chat (with real Orchestrator workflow & MCP backend)
  - Input validation, CORS, error handling, status codes.
"""

import pytest
import httpx
from backend.main import app


@pytest.fixture
async def api_client():
    """ASGI TestClient fixture for FastAPI application."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


class TestFastAPIBackend:
    """Test suite verifying FastAPI endpoints."""

    @pytest.mark.asyncio
    async def test_get_health_endpoint(self, api_client):
        """Test GET /api/v1/health endpoint."""
        res = await api_client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["app"] == "BugPilot"
        assert data["data_source"] in ["SQLite", "PostgreSQL", "Synthetic Demo Data"]

    @pytest.mark.asyncio
    async def test_get_agents_endpoint(self, api_client):
        """Test GET /api/v1/agents endpoint."""
        res = await api_client.get("/api/v1/agents")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] >= 6
        agent_names = [a["name"] for a in data["agents"]]
        assert "Orchestrator Agent" in agent_names
        assert "Bug Analyst" in agent_names
        assert "Risk Analyst" in agent_names

    @pytest.mark.asyncio
    async def test_get_tools_endpoint(self, api_client):
        """Test GET /api/v1/tools endpoint discovers tools dynamically from real MCP server."""
        res = await api_client.get("/api/v1/tools")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] >= 8
        tool_names = [t["name"] for t in data["tools"]]
        assert "get_bug_metrics" in tool_names
        assert "get_component_risk" in tool_names
        assert "get_bug_history" in tool_names
        assert "get_related_bugs" in tool_names

    @pytest.mark.asyncio
    async def test_post_chat_valid_query(self, api_client):
        """Test POST /api/v1/chat executes real Orchestrator workflow over MCP with tenant auth."""
        auth_res = await api_client.post("/api/v1/auth/login", json={"email": "admin@acme.com", "password": "AdminPass123!"})
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": "org-acme"}

        payload = {"message": "What are the biggest engineering risks?"}
        res = await api_client.post("/api/v1/chat", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert "execution_id" in data
        assert "request_id" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0
        assert any(a in data["agents_used"] for a in ["Risk Analyst", "Orchestrator Agent", "Bug Analyst"])
        assert any(t in data["tools_used"] for t in ["get_component_risk", "get_release_risk", "get_bug_metrics"])
        assert data["reflection"]["verdict"] in ["CONFIRM", "CORRECT"]
        assert data["data_source"] in ["PostgreSQL", "Synthetic Demo Data", "SQLite"]


    @pytest.mark.asyncio
    async def test_post_chat_unauthenticated_rejected(self, api_client):
        """Test POST /api/v1/chat rejects unauthenticated requests with 401."""
        res = await api_client.post("/api/v1/chat", json={"message": "Show bugs"})
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_post_chat_invalid_payload(self, api_client):
        """Test POST /api/v1/chat handles empty or missing message gracefully."""
        auth_res = await api_client.post("/api/v1/auth/login", json={"email": "admin@acme.com", "password": "AdminPass123!"})
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": "org-acme"}

        # Empty string
        res_empty = await api_client.post("/api/v1/chat", json={"message": ""}, headers=headers)
        assert res_empty.status_code in [400, 422]

        # Missing payload key
        res_missing = await api_client.post("/api/v1/chat", json={}, headers=headers)
        assert res_missing.status_code == 422

    @pytest.mark.asyncio
    async def test_cors_preflight(self, api_client):
        """Test CORS headers configuration."""
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        res = await api_client.options("/api/v1/chat", headers=headers)
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"

    @pytest.mark.asyncio
    async def test_metrics_scoped_filtering(self, api_client):
        """Phase 27: Test that project and component query parameters scope metrics properly."""
        auth_res = await api_client.post("/api/v1/auth/login", json={"email": "admin@acme.com", "password": "AdminPass123!"})
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": "org-acme"}

        # Unfiltered metrics
        res_all = await api_client.get("/api/v1/metrics", headers=headers)
        assert res_all.status_code == 200
        data_all = res_all.json()
        total_all = data_all["summary"]["total_bugs"]
        assert total_all >= 0

        # Scoped to project=BugPilot
        res_bp = await api_client.get("/api/v1/metrics?project=BugPilot", headers=headers)
        assert res_bp.status_code == 200
        data_bp = res_bp.json()
        total_bp = data_bp["summary"]["total_bugs"]
        assert total_bp <= total_all
        assert total_bp <= total_all

        # Scoped to project=BugPilot & component=Authentication
        res_auth = await api_client.get("/api/v1/metrics?project=BugPilot&component=Authentication", headers=headers)
        assert res_auth.status_code == 200
        data_auth = res_auth.json()
        total_auth = data_auth["summary"]["total_bugs"]
        assert total_auth <= total_bp

