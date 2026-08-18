"""
BugPilot — Unit & Regression Tests for Component Risk Analytics
================================================================
Verifies:
1. get_component_risk calculates open_issues from the same tenant-scoped bug records used by get_bug/search_bugs.
2. Authentication component shows its actual open-bug count (4 in org-acme: BP-101, BP-132, BP-133, BP-999).
3. Risk scores are evidence-based, formula-driven, and contain no hardcoded values.
4. Tenant isolation is strictly preserved (org-acme vs. other tenant).
5. MCP client get_component_risk returns open_issues and metrics matching underlying bug records.
"""

import pytest
from datetime import datetime, timedelta
from analytics.service import AnalyticsService
from models.bug import Bug, BugSeverity, BugStatus, BugPriority
from models.analytics import RiskMetric
from providers import get_data_provider, PostgresProvider
from mcp_client import MCPClient


class TestComponentRiskTenantScopingAndAccuracy:
    """Verifies component risk metrics match ground truth tenant-scoped bug records."""

    @pytest.mark.asyncio
    async def test_component_risk_open_issues_matches_bug_records(self):
        """Verify get_component_risk open_issues matches get_bugs open count for every component."""
        async with MCPClient() as client:
            # 1. Fetch component risks
            c_risk_data = await client.call_tool("get_component_risk", {"org_id": "org-acme"})
            comp_risks = c_risk_data.get("component_risks", [])
            assert len(comp_risks) > 0

            # 2. Fetch all bugs directly via provider for comparison
            provider = get_data_provider(org_id="org-acme")
            all_bugs = provider.get_bugs(limit=5000)

            for cr in comp_risks:
                comp_name = cr["name"]
                # Filter bugs for this component
                comp_bugs = [b for b in all_bugs if b.component.lower() == comp_name.lower()]
                expected_open_count = len([b for b in comp_bugs if b.is_open])
                expected_crit_high_open = len([
                    b for b in comp_bugs
                    if b.is_open and b.severity in {BugSeverity.CRITICAL.value, BugSeverity.HIGH.value}
                ])

                # Verify open_issues field and metrics match exact bug records
                assert cr["open_issues"] == expected_open_count, f"Mismatch for component {comp_name}"
                assert cr["metrics"]["open_bugs_count"] == expected_open_count
                assert cr["critical_high_issues"] == expected_crit_high_open
                assert cr["metrics"]["open_critical_high_count"] == expected_crit_high_open

    @pytest.mark.asyncio
    async def test_authentication_component_actual_open_bug_count(self):
        """Verify Authentication component reflects its actual 4 open critical bugs in org-acme."""
        async with MCPClient() as client:
            c_risk_data = await client.call_tool("get_component_risk", {
                "component": "Authentication",
                "org_id": "org-acme"
            })
            comp_risks = c_risk_data.get("component_risks", [])
            assert len(comp_risks) == 1

            auth_risk = comp_risks[0]
            assert auth_risk["name"] == "Authentication"
            assert auth_risk["open_issues"] == 4
            assert auth_risk["critical_high_issues"] == 4
            assert auth_risk["metrics"]["open_bugs_count"] == 4
            assert auth_risk["metrics"]["open_critical_high_count"] == 4
            assert auth_risk["risk_score"] > 0
            assert any("Critical/High" in r for r in auth_risk["reasons"])

            # Verify individual bugs match search_bugs and get_bug
            search_res = await client.call_tool("search_bugs", {"query": "auth", "limit": 20, "org_id": "org-acme"})
            auth_bugs = [b for b in search_res.get("bugs", []) if b.get("component") == "Authentication"]
            auth_bug_ids = {b["id"] for b in auth_bugs}

            expected_ids = {"BP-101", "BP-132", "BP-133", "BP-999"}
            assert expected_ids.issubset(auth_bug_ids)

            for b_id in expected_ids:
                single_bug = await client.call_tool("get_bug", {"bug_id": b_id, "org_id": "org-acme"})
                assert single_bug["found"] is True
                assert single_bug["bug"]["component"] == "Authentication"
                assert single_bug["bug"]["status"] == "open"

    def test_evidence_based_risk_score_formula_determinism(self):
        """Verify component risk formula evaluates dynamically based on evidence with no hardcoding."""
        now = datetime(2026, 8, 18, 12, 0, 0)
        from tests.unit.test_analytics import DummyDataProvider

        # Component A: 2 critical open bugs aged 20 days -> 2*15=30 + 10 (age 14-30d) = 40.0
        # Component B: 1 low open bug aged 2 days -> 1*5=5 + 0 = 5.0
        test_bugs = [
            Bug(
                id="TEST-1",
                title="Crit 1",
                severity=BugSeverity.CRITICAL,
                status=BugStatus.OPEN,
                component="CompA",
                created_at=now - timedelta(days=20),
                reporter="dev1"
            ),
            Bug(
                id="TEST-2",
                title="Crit 2",
                severity=BugSeverity.HIGH,
                status=BugStatus.OPEN,
                component="CompA",
                created_at=now - timedelta(days=20),
                reporter="dev1"
            ),
            Bug(
                id="TEST-3",
                title="Low 1",
                severity=BugSeverity.LOW,
                status=BugStatus.OPEN,
                component="CompB",
                created_at=now - timedelta(days=2),
                reporter="dev2"
            ),
        ]

        provider = DummyDataProvider(bugs=test_bugs, sprints=[])
        analytics = AnalyticsService(provider)
        payload = analytics.analyze(reference_time=now)

        comp_a = next(c for c in payload.component_risks if c.name == "CompA")
        comp_b = next(c for c in payload.component_risks if c.name == "CompB")

        assert comp_a.open_issues == 2
        assert comp_a.critical_high_issues == 2
        assert comp_a.risk_score == pytest.approx(40.0)

        assert comp_b.open_issues == 1
        assert comp_b.critical_high_issues == 0
        assert comp_b.risk_score == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_tenant_isolation_in_component_risk(self):
        """Verify tenant-scoped isolation: requesting an empty/different org returns only that org's data."""
        async with MCPClient() as client:
            empty_org_data = await client.call_tool("get_component_risk", {"org_id": "org-nonexistent"})
            assert empty_org_data.get("count") == 0
            assert len(empty_org_data.get("component_risks", [])) == 0
