"""
Phase 2 Test — Synthetic Data & Providers
==========================================
Verifies synthetic data generation, counts, schema constraints,
deterministic generation, MockJiraProvider lookups, filtering,
and status relationships.
"""

from __future__ import annotations

from datetime import datetime
import pytest

from models.bug import Bug, BugSeverity, BugStatus, BugPriority
from models.sprint import Sprint, SprintStatus
from data.generator import generate_synthetic_data
from providers.synthetic_provider import SyntheticProvider, MockJiraProvider


class TestSyntheticDataGeneration:
    """Verifies counts and metadata of generated data."""

    def test_generation_counts(self):
        bugs, sprints = generate_synthetic_data(seed=42)

        # ~1000 bugs (exactly 1000 in our implementation)
        assert len(bugs) == 1000
        # 20 sprints
        assert len(sprints) == 20

        # Check unique projects count (8 expected)
        projects = {b.project for b in bugs}
        assert len(projects) == 8
        assert "BP" in projects
        assert "API" in projects

        # Check unique components count (10 expected)
        components = {b.component for b in bugs}
        assert len(components) == 10

        # Check releases/fix versions (10 expected)
        fix_versions = {b.fix_version for b in bugs if b.fix_version}
        assert len(fix_versions) == 10

        # Check users pool (10 unique usernames expected)
        reporters = {b.reporter for b in bugs}
        assignees = {b.assignee for b in bugs if b.assignee}
        all_users = reporters.union(assignees)
        assert len(all_users) == 10

    def test_required_fields(self):
        bugs, _ = generate_synthetic_data(seed=42)

        for b in bugs:
            # Pydantic validates these on creation, but we explicitly assert here.
            assert b.key is not None and b.key != ""
            assert b.id == b.key
            assert b.project is not None and b.project != ""
            assert b.issue_type == "Bug"
            assert b.summary is not None and b.summary != ""
            assert b.title == b.summary
            assert b.description is not None
            assert b.priority in list(BugPriority)
            assert b.severity in list(BugSeverity)
            assert b.status in list(BugStatus)
            assert b.component is not None and b.component != ""
            assert b.reporter is not None and b.reporter != ""
            # sprint, fix_version, labels can be optional or default
            assert isinstance(b.labels, list)
            assert b.created_at is not None
            assert b.updated_at is not None
            assert b.reopened_count >= 0
            assert b.data_source == "Synthetic Demo Data"

    def test_deterministic_generation(self):
        """Verifies that two runs with the same seed produce identical datasets."""
        bugs_1, sprints_1 = generate_synthetic_data(seed=100)
        bugs_2, sprints_2 = generate_synthetic_data(seed=100)

        assert len(bugs_1) == len(bugs_2)
        assert len(sprints_1) == len(sprints_2)

        for b1, b2 in zip(bugs_1, bugs_2):
            assert b1.id == b2.id
            assert b1.title == b2.title
            assert b1.severity == b2.severity
            assert b1.status == b2.status
            assert b1.assignee == b2.assignee
            assert b1.created_at == b2.created_at

        for s1, s2 in zip(sprints_1, sprints_2):
            assert s1.id == s2.id
            assert s1.status == s2.status
            assert s1.start_date == s2.start_date
            assert s1.total_bugs == s2.total_bugs


class TestMockJiraProvider:
    """Verifies lookups, filtering, and search functionality in MockJiraProvider."""

    @pytest.fixture(scope="class")
    @staticmethod
    def provider() -> MockJiraProvider:
        return MockJiraProvider(seed=42)

    def test_get_bug_by_id(self, provider):
        # We know BP-1 (or other key) should exist
        bug = provider.get_bug("BP-1")
        if bug is None:
            # Let's search for any valid key if BP-1 didn't land on project BP
            bugs = provider.get_bugs(limit=5)
            assert len(bugs) > 0
            key = bugs[0].id
            bug = provider.get_bug(key)
        
        assert bug is not None
        assert isinstance(bug, Bug)
        # Case insensitive check
        assert provider.get_bug(bug.id.lower()) is not None

    def test_get_bug_nonexistent(self, provider):
        assert provider.get_bug("NONEXISTENT-99999") is None

    def test_get_sprint_by_id(self, provider):
        sprint = provider.get_sprint("SP-1")
        assert sprint is not None
        assert isinstance(sprint, Sprint)
        assert sprint.id == "SP-1"
        assert provider.get_sprint("sp-1") is not None

    def test_get_sprint_nonexistent(self, provider):
        assert provider.get_sprint("SP-999") is None

    def test_get_all_sprints(self, provider):
        sprints = provider.get_sprints()
        assert len(sprints) == 20

    def test_filtering_by_status(self, provider):
        bugs = provider.get_bugs(limit=1000, status="open")
        for b in bugs:
            assert b.status == BugStatus.OPEN.value

    def test_filtering_by_severity(self, provider):
        bugs = provider.get_bugs(limit=1000, severity="critical")
        for b in bugs:
            assert b.severity == BugSeverity.CRITICAL.value

    def test_filtering_by_project(self, provider):
        bugs = provider.get_bugs(limit=1000, project="BP")
        for b in bugs:
            assert b.project == "BP"

    def test_filtering_by_component(self, provider):
        bugs = provider.get_bugs(limit=1000, component="auth")
        for b in bugs:
            assert b.component == "auth"

    def test_filtering_by_sprint(self, provider):
        bugs = provider.get_bugs(limit=1000, sprint_id="SP-5")
        for b in bugs:
            assert b.sprint_id == "SP-5"

    def test_multiple_filters(self, provider):
        bugs = provider.get_bugs(limit=1000, project="BP", component="auth", status="resolved")
        for b in bugs:
            assert b.project == "BP"
            assert b.component == "auth"
            assert b.status == BugStatus.RESOLVED.value

    def test_search_bugs(self, provider):
        # Search for a component-specific keyword
        results = provider.search_bugs("Safari")
        assert len(results) > 0
        for b in results:
            assert "safari" in (b.title + b.summary + b.description).lower()

    def test_search_bugs_empty(self, provider):
        assert provider.search_bugs("   ") == []

    def test_search_bugs_nonexistent(self, provider):
        assert provider.search_bugs("xyzzy-nonexistent-string") == []


class TestWorkflowRelationships:
    """Verifies lifecycle rules (resolved_at timestamps, reopened status)."""

    def test_resolved_at_lifecycle(self):
        bugs, _ = generate_synthetic_data(seed=42)

        resolved_count = 0
        unresolved_count = 0

        for b in bugs:
            if b.status in {BugStatus.RESOLVED, BugStatus.CLOSED, BugStatus.WONT_FIX, BugStatus.DUPLICATE}:
                resolved_count += 1
                assert b.resolved_at is not None, f"Resolved issue {b.id} must have a resolved_at timestamp"
                assert b.resolved_at >= b.created_at, f"resolved_at ({b.resolved_at}) cannot be before created_at ({b.created_at})"
            else:
                unresolved_count += 1
                assert b.resolved_at is None, f"Unresolved issue {b.id} must not have a resolved_at timestamp"

        assert resolved_count > 0
        assert unresolved_count > 0

    def test_reopened_relationships(self):
        bugs, _ = generate_synthetic_data(seed=42)

        reopened_issues = [b for b in bugs if b.reopened_count > 0]
        assert len(reopened_issues) > 0

        for b in reopened_issues:
            # Reopened bugs represent issues that went back to dev/testing
            assert b.reopened_count >= 1
            # They should have been updated after creation because of the reopen activity
            assert b.updated_at >= b.created_at
