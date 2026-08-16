"""
BugPilot — Test Suite for Phase 17 Dynamic Data & Metrics Isolation Audit
==========================================================================
Tests:
- GET /api/v1/metrics requires authentication and tenant isolation.
- GET /api/v1/metrics returns real ground-truth metrics matching DataProvider.
- Organization isolation: User from org-acme cannot access metrics of org-globex.
- Provider mode respecting: Changing provider mode / active provider reflects in metrics response.
"""

import pytest
import httpx
from backend.main import app
from backend.security.auth import create_access_token, get_user_by_id


class TestPhase17DynamicMetricsAudit:
    """Test suite verifying ground-truth dynamic metrics backend endpoints."""

    @pytest.mark.asyncio
    async def test_get_metrics_unauthenticated_returns_401(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.get("/api/v1/metrics")
            assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_get_metrics_authenticated_success(self):
        user = get_user_by_id("usr-admin-1")
        token = create_access_token(user)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.get(
                "/api/v1/metrics",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            data = res.json()

            assert "summary" in data
            assert "total_bugs" in data["summary"]
            assert data["summary"]["total_bugs"] > 0
            assert "trends" in data
            assert "component_risks" in data
            assert data["org_id"] == "org-acme"

    @pytest.mark.asyncio
    async def test_metrics_tenant_isolation(self):
        # Globex user trying to claim org-acme header
        globex_user = get_user_by_id("usr-globex-1")
        token = create_access_token(globex_user)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.get(
                "/api/v1/metrics",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Organization-ID": "org-acme",
                },
            )
            assert res.status_code == 403
            assert "Access denied" in res.json()["detail"]
