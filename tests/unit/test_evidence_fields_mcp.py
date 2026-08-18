"""
Unit tests verifying enriched Jira-style evidence fields across DB, Providers, and MCP tools.
"""

import pytest
from backend.database.repository import init_db, db_get_issue_by_id_or_key, db_get_issues
from providers.postgres_provider import PostgresProvider
from providers.synthetic_provider import SyntheticProvider
from mcp_server.server import get_bug, search_bugs, get_bug_history, get_related_bugs


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    init_db()


def test_postgres_provider_evidence_fields():
    provider = PostgresProvider(org_id="org-acme")
    target_keys = ["BP-101", "BP-102", "BP-124", "BP-132", "BP-133", "BP-999"]

    for key in target_keys:
        bug = provider.get_bug(key)
        assert bug is not None, f"Bug {key} should exist in PostgresProvider"
        assert bug.root_cause is not None and len(bug.root_cause) > 10, f"{key} missing root_cause"
        assert bug.business_impact is not None and len(bug.business_impact) > 10, f"{key} missing business_impact"
        assert bug.steps_to_reproduce is not None and "1." in bug.steps_to_reproduce, f"{key} missing steps_to_reproduce"
        assert bug.expected_behavior is not None and len(bug.expected_behavior) > 5, f"{key} missing expected_behavior"
        assert bug.actual_behavior is not None and len(bug.actual_behavior) > 5, f"{key} missing actual_behavior"
        assert bug.environment in ["production", "staging", "development"], f"{key} missing environment"
        assert bug.affected_version is not None, f"{key} missing affected_version"
        assert bug.fix_version is not None, f"{key} missing fix_version"
        assert isinstance(bug.comments, list) and len(bug.comments) > 0, f"{key} missing comments"
        assert isinstance(bug.linked_issue_ids, list), f"{key} missing linked_issue_ids"


def test_mcp_get_bug_returns_evidence():
    for key in ["BP-124", "BP-133", "BP-101", "BP-102"]:
        res = get_bug(bug_id=key, org_id="org-acme")
        assert res["found"] is True
        b = res["bug"]
        assert "root_cause" in b and b["root_cause"] is not None
        assert "business_impact" in b and b["business_impact"] is not None
        assert "steps_to_reproduce" in b and b["steps_to_reproduce"] is not None
        assert "expected_behavior" in b and b["expected_behavior"] is not None
        assert "actual_behavior" in b and b["actual_behavior"] is not None
        assert "environment" in b and b["environment"] is not None
        assert "affected_version" in b and b["affected_version"] is not None
        assert "fix_version" in b and b["fix_version"] is not None
        assert "comments" in b and len(b["comments"]) > 0
        assert "linked_issue_ids" in b


def test_mcp_get_bug_history_returns_evidence():
    for key in ["BP-124", "BP-133", "BP-101"]:
        res = get_bug_history(bug_id=key, org_id="org-acme")
        assert res["found"] is True
        h = res["history"]
        assert "status_transitions" in h and len(h["status_transitions"]) > 0
        assert "comments" in h and len(h["comments"]) > 0
        assert "linked_issue_ids" in h
        assert "root_cause" in h


def test_mcp_get_related_bugs_returns_evidence():
    res = get_related_bugs(bug_id="BP-101", limit=5, org_id="org-acme")
    assert res["count"] > 0
    rel = res["related_bugs"]
    for rb in rel:
        assert "id" in rb
        assert "title" in rb
        assert "component" in rb
        assert "root_cause" in rb


def test_mcp_search_bugs_returns_evidence():
    provider = PostgresProvider(org_id="org-acme")
    results = provider.search_bugs(query="Payments")
    assert len(results) > 0
    found_124 = any(b.id == "BP-124" or b.key == "BP-124" for b in results)
    assert found_124, "BP-124 should be returned in Payments search"
    for b in results:
        assert b.root_cause is not None
        assert b.business_impact is not None
