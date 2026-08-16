"""
BugPilot — RBAC Permission Matrix Test Suite (Phase 2)
======================================================
Tests fine-grained role-based authorization across all 4 roles:
- ADMIN
- MANAGER
- DEVELOPER (and legacy ENGINEER alias)
- VIEWER

Verifies GET, POST, PUT, DELETE endpoints, registration escalation prevention, and tenant isolation.
"""

import pytest
import httpx
from backend.main import app
from backend.security.auth import (
    User,
    UserRole,
    create_access_token,
    get_user_by_id,
)


@pytest.fixture
def tokens():
    admin = User(id="usr-admin-1", email="admin@acme.com", full_name="Admin", role=UserRole.ADMIN, org_id="org-acme")
    manager = User(id="usr-mgr-1", email="manager@acme.com", full_name="Manager", role=UserRole.MANAGER, org_id="org-acme")
    developer = User(id="usr-dev-2", email="developer@acme.com", full_name="Dev", role=UserRole.DEVELOPER, org_id="org-acme")
    engineer = User(id="usr-dev-1", email="engineer@acme.com", full_name="Engineer", role=UserRole.ENGINEER, org_id="org-acme")
    viewer = User(id="usr-view-1", email="viewer@acme.com", full_name="Viewer", role=UserRole.VIEWER, org_id="org-acme")
    globex_admin = User(id="usr-globex-1", email="admin@globex.com", full_name="Globex Admin", role=UserRole.ADMIN, org_id="org-globex")

    return {
        "admin": create_access_token(admin),
        "manager": create_access_token(manager),
        "developer": create_access_token(developer),
        "engineer": create_access_token(engineer),
        "viewer": create_access_token(viewer),
        "globex_admin": create_access_token(globex_admin),
    }


class TestRBACPermissionMatrix:
    """Automated verification of the RBAC Permission Matrix."""

    @pytest.mark.asyncio
    async def test_admin_permissions_full_access(self, tokens):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            headers = {"Authorization": f"Bearer {tokens['admin']}", "X-Organization-ID": "org-acme"}

            # GET
            get_res = await client.get("/api/v1/issues", headers=headers)
            assert get_res.status_code == 200

            # POST
            post_res = await client.post(
                "/api/v1/issues",
                headers=headers,
                json={"title": "Admin Test Issue", "project": "BugPilot", "component": "Core", "priority": "High"},
            )
            assert post_res.status_code == 201
            issue_id = post_res.json()["id"]

            # PUT
            put_res = await client.put(
                f"/api/v1/issues/{issue_id}",
                headers=headers,
                json={"title": "Admin Updated Issue"},
            )
            assert put_res.status_code == 200
            assert put_res.json()["title"] == "Admin Updated Issue"

            # DELETE
            del_res = await client.delete(f"/api/v1/issues/{issue_id}", headers=headers)
            assert del_res.status_code == 200

    @pytest.mark.asyncio
    async def test_manager_permissions_full_access(self, tokens):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            headers = {"Authorization": f"Bearer {tokens['manager']}", "X-Organization-ID": "org-acme"}

            # GET
            assert (await client.get("/api/v1/issues", headers=headers)).status_code == 200

            # POST
            post_res = await client.post(
                "/api/v1/issues",
                headers=headers,
                json={"title": "Manager Test Issue", "project": "BugPilot", "component": "Core"},
            )
            assert post_res.status_code == 201
            issue_id = post_res.json()["id"]

            # PUT
            assert (await client.put(f"/api/v1/issues/{issue_id}", headers=headers, json={"status": "In Progress"})).status_code == 200

            # DELETE
            assert (await client.delete(f"/api/v1/issues/{issue_id}", headers=headers)).status_code == 200

    @pytest.mark.asyncio
    async def test_developer_permissions_cannot_delete(self, tokens):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            headers = {"Authorization": f"Bearer {tokens['developer']}", "X-Organization-ID": "org-acme"}

            # GET
            assert (await client.get("/api/v1/issues", headers=headers)).status_code == 200

            # POST
            post_res = await client.post(
                "/api/v1/issues",
                headers=headers,
                json={"title": "Developer Test Issue", "project": "BugPilot", "component": "Core"},
            )
            assert post_res.status_code == 201
            issue_id = post_res.json()["id"]

            # PUT
            assert (await client.put(f"/api/v1/issues/{issue_id}", headers=headers, json={"status": "Resolved"})).status_code == 200

            # DELETE -> Must return 403 Forbidden
            del_res = await client.delete(f"/api/v1/issues/{issue_id}", headers=headers)
            assert del_res.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_permissions_read_only(self, tokens):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            headers = {"Authorization": f"Bearer {tokens['viewer']}", "X-Organization-ID": "org-acme"}

            # GET -> Allowed
            assert (await client.get("/api/v1/issues", headers=headers)).status_code == 200

            # POST -> 403 Forbidden
            post_res = await client.post(
                "/api/v1/issues",
                headers=headers,
                json={"title": "Viewer Unauthorized Issue"},
            )
            assert post_res.status_code == 403

            # PUT -> 403 Forbidden
            put_res = await client.put(f"/api/v1/issues/iss-101", headers=headers, json={"status": "Closed"})
            assert put_res.status_code == 403

            # DELETE -> 403 Forbidden
            del_res = await client.delete("/api/v1/issues/iss-101", headers=headers)
            assert del_res.status_code == 403

    @pytest.mark.asyncio
    async def test_registration_prevents_privilege_escalation(self):
        import uuid
        test_email = f"hacker-{uuid.uuid4().hex[:4]}@acme.com"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            # Attempting to register as Admin
            res = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": "HackerPass123!",
                    "full_name": "Hacker User",
                    "role": "Admin",
                    "org_id": "org-acme",
                },
            )
            assert res.status_code == 200
            # Must be forced to Viewer role
            assert res.json()["role"] == "Viewer"

    @pytest.mark.asyncio
    async def test_cross_tenant_isolation(self, tokens):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            # Globex Admin trying to pass Acme headers
            headers = {"Authorization": f"Bearer {tokens['globex_admin']}", "X-Organization-ID": "org-acme"}
            res = await client.get("/api/v1/issues", headers=headers)
            assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_get_supported_roles_endpoint(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            res = await client.get("/api/v1/auth/roles")
            assert res.status_code == 200
            roles = res.json()
            assert "ADMIN" in roles
            assert "MANAGER" in roles
            assert "DEVELOPER" in roles
            assert "VIEWER" in roles

    @pytest.mark.asyncio
    async def test_missing_jwt_returns_401(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            res = await client.get("/api/v1/issues")
            assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_seeded_users_preserve_roles(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            admin_res = await client.post("/api/v1/auth/login", json={"email": "admin@acme.com", "password": "AdminPass123!"})
            assert admin_res.status_code == 200
            assert admin_res.json()["user"]["role"] == "Admin"

            mgr_res = await client.post("/api/v1/auth/login", json={"email": "manager@acme.com", "password": "ManagerPass123!"})
            assert mgr_res.status_code == 200
            assert mgr_res.json()["user"]["role"] == "Manager"

            dev_res = await client.post("/api/v1/auth/login", json={"email": "developer@acme.com", "password": "DeveloperPass123!"})
            assert dev_res.status_code == 200
            assert dev_res.json()["user"]["role"] == "Developer"

            view_res = await client.post("/api/v1/auth/login", json={"email": "viewer@acme.com", "password": "ViewerPass123!"})
            assert view_res.status_code == 200
            assert view_res.json()["user"]["role"] == "Viewer"
