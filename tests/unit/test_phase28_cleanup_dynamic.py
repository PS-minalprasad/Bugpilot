"""
BugPilot — Phase 28 Unit & Integration Test Suite
===================================================
Tests for:
- PostgreSQL IssueModel schema & repository CRUD
- PostgresProvider data mapping & filtering
- Issue CRUD API endpoints (/api/v1/issues)
- Multi-tenant isolation (org-acme vs org-globex)
- Unauthenticated access prevention (401)
- MCP tool & Agent integration with PostgreSQL data source
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.repository import (
    db_create_issue,
    db_get_issues,
    db_get_issue_by_id_or_key,
    db_update_issue,
    db_delete_issue,
)
from providers.postgres_provider import PostgresProvider
from mcp_server.server import get_bug_metrics, search_bugs

client = TestClient(app)


def test_postgres_repository_crud():
    # 1. Create issue
    issue = db_create_issue(
        org_id="org-acme",
        data={
            "id": "iss-test-1",
            "issue_key": "BP-TEST1",
            "title": "Test Auth Leak",
            "description": "Test description",
            "status": "Open",
            "priority": "High",
            "severity": "Critical",
            "project": "BugPilot",
            "component": "Security",
            "assignee": "Acme Dev",
        },
    )
    assert issue.id == "iss-test-1"
    assert issue.organization_id == "org-acme"

    # 2. Get issue
    fetched = db_get_issue_by_id_or_key("iss-test-1", org_id="org-acme")
    assert fetched is not None
    assert fetched.title == "Test Auth Leak"

    # 3. Update issue
    updated = db_update_issue("iss-test-1", org_id="org-acme", data={"status": "Resolved"})
    assert updated is not None
    assert updated.status == "Resolved"

    # 4. Delete issue
    deleted = db_delete_issue("iss-test-1", org_id="org-acme")
    assert deleted is True
    assert db_get_issue_by_id_or_key("iss-test-1", org_id="org-acme") is None


def test_postgres_provider_data_source():
    provider = PostgresProvider(org_id="org-acme")
    bugs = provider.get_bugs(limit=10)
    assert len(bugs) > 0
    for bug in bugs:
        assert bug.data_source == "PostgreSQL"


def test_issues_api_endpoints():
    # Login as Acme Admin
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@acme.com", "password": "AdminPass123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. POST /api/v1/issues (Create Issue)
    create_resp = client.post(
        "/api/v1/issues",
        headers=headers,
        json={
            "title": "API Create Test Bug",
            "description": "Created via test suite",
            "status": "Open",
            "priority": "High",
            "severity": "Critical",
            "project": "BugPilot",
            "component": "Authentication",
            "assignee": "Acme Dev",
        },
    )
    assert create_resp.status_code == 201
    issue_data = create_resp.json()
    issue_id = issue_data["id"]
    assert issue_data["title"] == "API Create Test Bug"
    assert issue_data["organization_id"] == "org-acme"

    # 2. GET /api/v1/issues (List Issues)
    list_resp = client.get("/api/v1/issues", headers=headers)
    assert list_resp.status_code == 200
    issues_list = list_resp.json()
    assert any(i["id"] == issue_id for i in issues_list)

    # 3. GET /api/v1/issues/{id} (Get Detail)
    detail_resp = client.get(f"/api/v1/issues/{issue_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == issue_id

    # 4. PUT /api/v1/issues/{id} (Update Issue)
    update_resp = client.put(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"status": "Resolved"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "Resolved"

    # 5. DELETE /api/v1/issues/{id} (Delete Issue)
    del_resp = client.delete(f"/api/v1/issues/{issue_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

    # Verify deleted
    get_del = client.get(f"/api/v1/issues/{issue_id}", headers=headers)
    assert get_del.status_code == 404


def test_issues_api_unauthenticated_and_multitenancy():
    # 1. Unauthenticated GET /api/v1/issues -> 401
    unauth_resp = client.get("/api/v1/issues")
    assert unauth_resp.status_code == 401

    # 2. Login as Acme Admin
    login_acme = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@acme.com", "password": "AdminPass123!"},
    )
    token_acme = login_acme.json()["access_token"]

    # 3. Wrong Tenant Request X-Organization-ID: org-globex -> 403
    wrong_tenant_resp = client.get(
        "/api/v1/issues",
        headers={
            "Authorization": f"Bearer {token_acme}",
            "X-Organization-ID": "org-globex",
        },
    )
    assert wrong_tenant_resp.status_code == 403


def test_mcp_tools_use_postgres_provider():
    metrics = get_bug_metrics(org_id="org-acme")
    assert metrics["data_source"] == "PostgreSQL"
    assert "total_bugs" in metrics["summary"]

    search_res = search_bugs(query="Authentication", org_id="org-acme")
    assert search_res["data_source"] == "PostgreSQL"
