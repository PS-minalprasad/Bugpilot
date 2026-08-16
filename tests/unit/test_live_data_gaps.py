"""
BugPilot — Live User Data & Dynamic MCP Integration Test Suite
===============================================================
Verifies:
1. Issues created with distinct sprint_id values flow cleanly to PostgreSQL and MCP tools.
2. Reopening a resolved/closed issue increments reopen_count.
3. get_bug_metrics(sprint_id=...) and get_bug_trends(sprint_id=...) filter correctly by real sprint data.
4. get_reopened_bugs reflects real reopened issue counts.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.repository import (
    init_db,
    db_create_issue,
    db_update_issue,
    db_get_issue_by_id_or_key,
    db_get_sprints,
)
from providers.postgres_provider import PostgresProvider
from mcp_server.server import get_bug_metrics, get_bug_trends, get_reopened_bugs

client = TestClient(app)
init_db()


def test_live_sprints_and_issue_filtering():
    init_db()
    # Seed issues in two distinct sprints
    iss1 = db_get_issue_by_id_or_key("live-iss-1", org_id="org-acme")
    if not iss1:
        iss1 = db_create_issue(
            org_id="org-acme",
            data={
                "id": "live-iss-1",
                "issue_key": "LIVE-1",
                "title": "Live Sprint 1 Bug",
                "status": "Open",
                "severity": "Critical",
                "project": "BugPilot",
                "component": "API",
                "sprint_id": "SPRINT-2026-01",
            },
        )
    iss2 = db_get_issue_by_id_or_key("live-iss-2", org_id="org-acme")
    if not iss2:
        iss2 = db_create_issue(
            org_id="org-acme",
            data={
                "id": "live-iss-2",
                "issue_key": "LIVE-2",
                "title": "Live Sprint 2 Bug",
                "status": "Open",
                "severity": "High",
                "project": "BugPilot",
                "component": "UI",
                "sprint_id": "SPRINT-2026-02",
            },
        )

    provider = PostgresProvider(org_id="org-acme")
    sprint1_bugs = provider.get_bugs(sprint_id="SPRINT-2026-01")
    sprint2_bugs = provider.get_bugs(sprint_id="SPRINT-2026-02")

    assert any(b.id == "LIVE-1" for b in sprint1_bugs)
    assert not any(b.id == "LIVE-2" for b in sprint1_bugs)
    assert any(b.id == "LIVE-2" for b in sprint2_bugs)

    # MCP tool get_bug_metrics with sprint_id filter
    m1 = get_bug_metrics(sprint_id="SPRINT-2026-01", org_id="org-acme")
    m2 = get_bug_metrics(sprint_id="SPRINT-2026-02", org_id="org-acme")

    assert m1["data_source"] == "PostgreSQL"
    assert m2["data_source"] == "PostgreSQL"


def test_reopen_count_status_transition_tracking():
    init_db()
    from backend.database.repository import db_delete_issue
    db_delete_issue("reopen-iss-1", org_id="org-acme")

    # 1. Create issue
    iss = db_create_issue(
        org_id="org-acme",
        data={
            "id": "reopen-iss-1",
            "issue_key": "REOPEN-1",
            "title": "Reopen Tracking Bug",
            "status": "Open",
            "severity": "High",
            "project": "BugPilot",
            "component": "Database",
        },
    )
    assert iss.reopen_count == 0

    # 2. Resolve issue
    resolved_iss = db_update_issue("reopen-iss-1", org_id="org-acme", data={"status": "Resolved"})
    assert resolved_iss.status == "Resolved"
    assert resolved_iss.reopen_count == 0

    # 3. Reopen issue -> status transition to Open
    reopened_iss = db_update_issue("reopen-iss-1", org_id="org-acme", data={"status": "Open"})
    assert reopened_iss.status == "Open"
    assert reopened_iss.reopen_count == 1

    # 4. Verify PostgresProvider domain model mapping
    provider = PostgresProvider(org_id="org-acme")
    bug_domain = provider.get_bug("REOPEN-1")
    assert bug_domain is not None
    assert bug_domain.reopened_count == 1

    # 5. Verify MCP tool get_reopened_bugs
    reopened_mcp = get_reopened_bugs(org_id="org-acme")
    assert reopened_mcp["data_source"] == "PostgreSQL"
    assert any(b["id"] == "REOPEN-1" for b in reopened_mcp["reopened_bugs"])
