"""
BugPilot — Goal-Based Intent Routing & Accuracy Regression Suite
================================================================
Verifies multiple natural-language query variations for all 10 intents:
1. SPECIFIC_BUG
2. BUG_SEARCH
3. METRICS
4. TREND
5. REOPENED_BUGS
6. COMPONENT_ANALYSIS
7. RISK
8. RELEASE_RISK
9. AGING_BUGS
10. GENERAL_REPORT

Pipeline verified for each:
Query -> Intent Classification -> Specialist Agent -> MCP Tool -> Evidence Grounding -> Final Output
"""

import pytest

from mcp_client.client import MCPClient
from agents.orchestrator import OrchestratorAgent
from backend.database.repository import init_db, db_create_issue, db_get_issue_by_id_or_key


@pytest.fixture(autouse=True)
def setup_test_data():
    init_db()
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


# ==========================================
# 1. SPECIFIC BUG INTENT VARIATIONS
# ==========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_tool,expected_agent", [
    ("What is the status of BP-999?", "get_bug", "Bug Analyst"),
    ("Tell me about the Authentication bug", "search_bugs", "Bug Analyst"),
    ("Show details for token validation error", "search_bugs", "Bug Analyst"),
    ("Details of BP-999", "get_bug", "Bug Analyst"),
])
async def test_specific_bug_variations(query, expected_tool, expected_agent):
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run(query)

        assert res.intent == "SPECIFIC_BUG"
        assert expected_agent in [s.agent_name for s in res.execution_steps]
        assert expected_tool in [s.tool_name for s in res.execution_steps]
        assert res.error is None
        assert "BP-999" in res.final_answer or "Authentication" in res.final_answer or "token" in res.final_answer


# ==========================================
# 2. BUG SEARCH INTENT VARIATIONS
# ==========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Search for all open billing bugs",
    "Find critical severity bugs in the project",
    "Search issues matching authentication",
    "List all open bugs in Billing",
])
async def test_bug_search_variations(query):
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run(query)

        assert res.intent in ["BUG_SEARCH", "SPECIFIC_BUG"]
        assert "Bug Analyst" in [s.agent_name for s in res.execution_steps]
        assert "search_bugs" in [s.tool_name for s in res.execution_steps]
        assert res.error is None


# ==========================================
# 3. METRICS INTENT VARIATIONS
# ==========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "How many total bugs do we have?",
    "How many bugs are currently open?",
    "Show bug count and severity breakdown",
    "What is the total bug distribution?",
])
async def test_metrics_variations(query):
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run(query)

        assert res.intent in ["METRIC", "METRICS"]
        assert "Bug Analyst" in [s.agent_name for s in res.execution_steps]
        assert "get_bug_metrics" in [s.tool_name for s in res.execution_steps]
        assert "total" in res.final_answer.lower()


# ==========================================
# 4. TREND INTENT VARIATIONS
# ==========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "What is the current bug trend?",
    "Are Authentication bugs increasing this sprint?",
    "Show historical bug velocity over time",
    "Is our bug resolution trend decreasing?",
])
async def test_trend_variations(query):
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run(query)

        assert res.intent == "TREND"
        assert "Trend Analyst" in [s.agent_name for s in res.execution_steps]
        assert "get_bug_trends" in [s.tool_name for s in res.execution_steps]
        assert "trend" in res.final_answer.lower() or "period" in res.final_answer.lower()


# ==========================================
# 5. REOPENED BUGS INTENT VARIATIONS
# ==========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Which bugs have been reopened multiple times?",
    "Show reopened bug list and churn",
    "What is our reopen rate?",
])
async def test_reopened_bugs_variations(query):
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run(query)

        assert res.intent == "REOPENED_BUGS"
        assert "Trend Analyst" in [s.agent_name for s in res.execution_steps]
        assert "get_reopened_bugs" in [s.tool_name for s in res.execution_steps]
        assert "reopened" in res.final_answer.lower()


# ==========================================
# 6. COMPONENT RISK INTENT VARIATIONS
# ==========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Which component has the highest risk?",
    "Analyze component risk for Authentication",
    "What is our riskiest component?",
    "Show component danger scores",
])
async def test_component_risk_variations(query):
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run(query)

        assert res.intent in ["COMPONENT_ANALYSIS", "RISK"]
        assert "Risk Analyst" in [s.agent_name for s in res.execution_steps]
        assert "get_component_risk" in [s.tool_name for s in res.execution_steps]
        assert "risk" in res.final_answer.lower()


# ==========================================
# 7. RELEASE RISK INTENT VARIATIONS
# ==========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Is the upcoming release safe?",
    "Can we deploy to production safely?",
    "Evaluate release readiness and deploy risk",
    "What is our release risk status?",
])
async def test_release_risk_variations(query):
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run(query)

        assert res.intent == "RELEASE_RISK"
        assert "Risk Analyst" in [s.agent_name for s in res.execution_steps]
        assert "get_release_risk" in [s.tool_name for s in res.execution_steps] or "get_component_risk" in [s.tool_name for s in res.execution_steps]
        assert "release" in res.final_answer.lower() or "risk" in res.final_answer.lower()


# ==========================================
# 8. AGING BUGS INTENT VARIATIONS
# ==========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Show me old unresolved aging bugs",
    "Which bugs are stagnant and older than 14 days?",
    "List aging tickets in the backlog",
])
async def test_aging_bugs_variations(query):
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run(query)

        assert res.intent == "AGING_BUGS"
        assert "Risk Analyst" in [s.agent_name for s in res.execution_steps]
        assert "get_aging_bugs" in [s.tool_name for s in res.execution_steps]
        assert "aging" in res.final_answer.lower() or "old" in res.final_answer.lower()


# ==========================================
# 9. GENERAL REPORT INTENT VARIATIONS
# ==========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Give me a complete engineering health report",
    "Generate an executive summary report for leadership",
    "Provide a full system report across all metrics",
])
async def test_general_report_variations(query):
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        res = await orchestrator.run(query)

        assert res.intent in ["GENERAL_REPORT", "REPORT"]
        assert len(res.execution_steps) >= 2
        assert "get_bug_metrics" in [s.tool_name for s in res.execution_steps]
        assert "get_component_risk" in [s.tool_name for s in res.execution_steps]
