"""
BugPilot — Query Intent, Report Generation & Production Live Lifecycle Test Suite
===================================================================================
Verifies:
1. Specific bug lookup.
2. Bug ID lookup.
3. Metrics query.
4. Trend query.
5. Risk query.
6. Release risk query.
7. Component analysis query.
8. Missing bug query.
9. MCP tool selection logic.
10. Agent routing logic.
11. Data grounding (facts separated from inference).
12. Reflection validation.
13. Structured report generation (9 sections for specific bugs).
14. Hallucination prevention.
15. Existing functionality regression.
16. Live CRUD Bug Lifecycle (Create -> Query Live -> Update -> Query Live Updated -> Delete -> Query Live Deleted).
"""

import pytest

from mcp_client.client import MCPClient
from agents.orchestrator import OrchestratorAgent
from agents.reporting import ReflectionAgent, ReportAgent
from backend.database.repository import (
    init_db,
    db_create_issue,
    db_update_issue,
    db_delete_issue,
    db_get_issue_by_id_or_key,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    # Seed a known test bug if not already existing
    iss = db_get_issue_by_id_or_key("iss-auth-99", org_id="org-acme")
    if not iss:
        db_create_issue(
            org_id="org-acme",
            data={
                "id": "iss-auth-99",
                "issue_key": "BP-999",
                "title": "Authentication token validation error",
                "description": "Token exchange fails on boundary expiration.",
                "status": "Open",
                "priority": "High",
                "severity": "Critical",
                "project": "BugPilot",
                "component": "Authentication",
                "assignee": "Auth Dev",
                "reporter": "Auth Reporter",
            },
        )


@pytest.mark.asyncio
async def test_1_specific_bug_query():
    """1. Test specific bug query retrieves specific bug report."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("Tell me about the Authentication bug")

        assert res.intent in ["SPECIFIC_BUG", "REPORT"]
        assert "BP-999" in res.final_answer or "iss-auth-99" in res.final_answer or "Authentication" in res.final_answer
        assert "Total 10 bugs" not in res.final_answer


@pytest.mark.asyncio
async def test_2_bug_id_query():
    """2. Test querying by specific bug ID (BP-999)."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("What is the status of BP-999?")

        assert res.intent == "SPECIFIC_BUG"
        assert "BP-999" in res.final_answer
        assert "Bug Analysis Report" in res.final_answer


@pytest.mark.asyncio
async def test_3_metric_query():
    """3. Test metric query uses get_bug_metrics."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("How many bugs are open?")

        assert res.intent in ["METRIC", "METRICS"]
        assert "get_bug_metrics" in [s.tool_name for s in res.execution_steps]


@pytest.mark.asyncio
async def test_4_trend_query():
    """4. Test trend query uses get_bug_trends."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("What is the current bug trend?")

        assert res.intent == "TREND"
        assert "get_bug_trends" in [s.tool_name for s in res.execution_steps]


@pytest.mark.asyncio
async def test_5_risk_query():
    """5. Test risk query uses get_component_risk or get_aging_bugs."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("Which component has the highest risk?")

        assert res.intent in ["RISK", "COMPONENT_ANALYSIS"]
        assert "get_component_risk" in [s.tool_name for s in res.execution_steps] or "get_aging_bugs" in [s.tool_name for s in res.execution_steps]


@pytest.mark.asyncio
async def test_6_release_risk_query():
    """6. Test release risk query routes to release risk evaluation."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("Is this release safe?")

        assert res.intent in ["RISK", "RELEASE_RISK", "REPORT"]
        assert len(res.execution_steps) > 0


@pytest.mark.asyncio
async def test_7_component_analysis_query():
    """7. Test component analysis query routes to component risk."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("Analyze component risk for Authentication")

        assert res.intent in ["RISK", "COMPONENT_ANALYSIS", "REPORT"]
        assert "get_component_risk" in [s.tool_name for s in res.execution_steps]


@pytest.mark.asyncio
async def test_8_no_matching_bug_query():
    """8. Test querying a non-existent bug returns clear 'couldn't find' message."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("Tell me about NonExistentBugXyz999")

        assert res.intent == "SPECIFIC_BUG"
        assert "couldn't find a bug" in res.final_answer.lower() or "no bug found" in res.final_answer.lower()


@pytest.mark.asyncio
async def test_9_mcp_tool_selection_logic():
    """9. Test Orchestrator classifies intent and maps to proper MCP tool."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)

        classified_bug = orchestrator._classify_intent("Tell me about the login bug")
        assert classified_bug["intent"] == "SPECIFIC_BUG"

        classified_metric = orchestrator._classify_intent("How many critical bugs do we have?")
        assert classified_metric["intent"] in ["METRIC", "METRICS"]

        classified_trend = orchestrator._classify_intent("Are bugs increasing this sprint?")
        assert classified_trend["intent"] == "TREND"


@pytest.mark.asyncio
async def test_10_agent_routing():
    """10. Verify Orchestrator selects correct specialist agents based on intent."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("What is the status of BP-999?")

        agent_names = [s.agent_name for s in res.execution_steps]
        assert "Bug Analyst" in agent_names


@pytest.mark.asyncio
async def test_11_data_grounding():
    """11. Test response contains ground-truth fields from retrieved bug and separates facts from analysis."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("What is the status of BP-999?")

        assert "Facts" in res.final_answer or "Bug Details" in res.final_answer
        assert "open" in res.final_answer.lower()
        assert "critical" in res.final_answer.lower() or "high" in res.final_answer.lower()


def test_12_reflection_validation():
    """12. Test ReflectionAgent checks specific bug responses and missing bug messages."""
    reflection = ReflectionAgent()

    # Valid response
    eval_ok, _ = reflection.reflect(
        answer="# Bug Analysis Report — BP-999\n- Bug ID: BP-999\n- Status: Open",
        evidence={"intent": "SPECIFIC_BUG", "search_results": [{"id": "BP-999", "title": "Authentication token validation error"}]},
    )
    assert eval_ok.verdict == "CONFIRM"
    assert eval_ok.quality_score >= 0.90

    # Missing bug valid response
    eval_missing_ok, _ = reflection.reflect(
        answer="I couldn't find a bug matching 'NonExistent'. Please provide a bug ID or more details.",
        evidence={"intent": "SPECIFIC_BUG", "search_results": []},
    )
    assert eval_missing_ok.verdict == "CONFIRM"


def test_13_report_generation_structure():
    """13. Test ReportAgent creates structured AnalysisReport."""
    agent = ReportAgent()
    report = agent.generate_report(
        query="Give me a complete bug health report",
        bug_evidence={"summary": {"total_bugs": 10, "open_bugs": 5, "critical_high_bugs": 3}},
    )

    assert report.report_id.startswith("report-")
    assert report.executive_summary.title == "Executive Summary"
    assert "10" in report.bug_analysis.content


@pytest.mark.asyncio
async def test_14_hallucination_prevention():
    """14. Test response does not fabricate root cause or numerical scores."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("What is the status of BP-999?")

        # Check that response reflects retrieved evidence
        assert "root cause" in res.final_answer.lower() or "does not provide enough evidence" in res.final_answer.lower()


@pytest.mark.asyncio
async def test_15_existing_functionality_regression():
    """15. Test execution steps and trace metadata remain complete."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run("Tell me about the Authentication bug")

        assert res.execution_id is not None
        assert res.elapsed_seconds >= 0.0
        assert len(res.execution_steps) > 0


@pytest.mark.asyncio
async def test_16_live_crud_bug_lifecycle():
    """16. Explicitly test Live CRUD: Create bug -> Query AI -> Update bug -> Query AI -> Delete bug -> Query AI."""
    live_bug_id = "iss-live-crud-77"
    live_bug_key = "LIVE-777"
    org_id = "org-acme"

    # Ensure clean state
    db_delete_issue(issue_id=live_bug_id, org_id=org_id)

    # Step A: Create bug
    db_create_issue(
        org_id=org_id,
        data={
            "id": live_bug_id,
            "issue_key": live_bug_key,
            "title": "Live Payment Gateway Timeout Exception",
            "description": "Payment webhook timeouts under high concurrency.",
            "status": "Open",
            "priority": "High",
            "severity": "Critical",
            "project": "BugPilot",
            "component": "Billing",
            "assignee": "Payment Dev",
            "reporter": "QA Lead",
        },
    )

    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)

        # Step B: Query immediately and verify AI finds live bug
        res1 = await orchestrator.run(f"What is the status of {live_bug_key}?")
        assert res1.intent == "SPECIFIC_BUG"
        assert live_bug_key in res1.final_answer
        assert "Live Payment Gateway Timeout Exception" in res1.final_answer
        assert "open" in res1.final_answer.lower()

        # Step C: Update bug in database
        db_update_issue(
            issue_id=live_bug_id,
            org_id=org_id,
            data={
                "title": "Live Payment Gateway Timeout Exception RESOLVED",
                "status": "Resolved",
            },
        )

        # Step D: Query again and verify AI retrieves updated state
        res2 = await orchestrator.run(f"What is the status of {live_bug_key}?")
        assert res2.intent == "SPECIFIC_BUG"
        assert live_bug_key in res2.final_answer
        assert "resolved" in res2.final_answer.lower()

        # Step E: Delete bug from database
        deleted_ok = db_delete_issue(issue_id=live_bug_id, org_id=org_id)
        assert deleted_ok is True

        # Step F: Query again and verify AI handles deleted state
        res3 = await orchestrator.run(f"What is the status of {live_bug_key}?")
        assert res3.intent == "SPECIFIC_BUG"
        assert "couldn't find a bug" in res3.final_answer.lower() or "no bug found" in res3.final_answer.lower()
