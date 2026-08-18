"""
BugPilot — Unit & Regression Tests for Component-Risk Query Handling
====================================================================
Verifies:
1. Route component-risk/ranking queries to get_component_risk.
2. Do not call search_bugs unless the user is actually asking for bugs/issues.
3. If get_component_risk returns valid records, use them as authoritative evidence for the final answer.
4. For 'highest risk' component queries, identify the maximum risk score and explain reasoning.
5. Example expected result: Authentication = 45/100, 4 open issues -> highest risk -> investigate Authentication first.
6. Does not produce 'No matching issues found' when component risk records are retrieved.
"""

import pytest
from agents.orchestrator import OrchestratorAgent
from mcp_client import MCPClient


class TestComponentRiskQueryRoutingAndSynthesis:
    """Verifies proper classification, tool selection, and synthesis for component risk queries."""

    @pytest.mark.asyncio
    async def test_query_classification_component_risk_vs_bug_comparison(self):
        """Verify distinct classification between component risk queries and bug comparison queries."""
        async with MCPClient() as client:
            orchestrator = OrchestratorAgent(mcp_client=client)

            # Component risk queries
            comp_queries = [
                "Which component has the highest risk?",
                "What is the riskiest component?",
                "Rank components by risk",
                "Show component risk analysis",
                "Highest risk component in the system",
                "Which component is most dangerous?",
            ]
            for q in comp_queries:
                assert orchestrator._is_component_risk_query(q) is True, f"Failed for {q}"
                assert orchestrator._is_bug_comparison_query(q) is False, f"Should not be bug comparison for {q}"
                intent = orchestrator._classify_intent(q)
                assert intent["intent"] == "COMPONENT_ANALYSIS"
                assert intent["tool"] == "get_component_risk"

            # Bug comparison queries
            bug_queries = [
                "analyze authentication bugs and identify the highest-risk issue",
                "compare payment bugs and find the most critical one",
                "which bug in billing has the highest risk?",
                "evaluate all candidate bugs",
            ]
            for q in bug_queries:
                assert orchestrator._is_component_risk_query(q) is False, f"Should not be component risk for {q}"
                assert orchestrator._is_bug_comparison_query(q) is True, f"Should be bug comparison for {q}"

    @pytest.mark.asyncio
    async def test_highest_risk_component_orchestrator_execution(self):
        """Verify full orchestrator execution for 'Which component has the highest risk?'."""
        async with MCPClient() as client:
            orchestrator = OrchestratorAgent(mcp_client=client, max_iterations=5)
            result = await orchestrator.run("Which component has the highest risk?")

            assert result.status == "success"
            answer = result.final_answer

            # 1. Authoritative component evidence: Authentication is highest risk
            assert "Authentication" in answer
            assert "45" in answer or "45.0" in answer
            assert "4 open" in answer.lower() or "4" in answer

            # 2. Contains clear recommendation to investigate Authentication first
            assert "investigate" in answer.lower() or "prioritize" in answer.lower()

            # 3. Does NOT claim no bugs were found
            assert "no matching issues found" not in answer.lower()
            assert "couldn't find any bugs" not in answer.lower()

            # 4. Verified tool call trace called get_component_risk and NOT search_bugs
            tools_called = [step.tool_name for step in result.execution_steps]
            assert "get_component_risk" in tools_called
            assert "search_bugs" not in tools_called

    @pytest.mark.asyncio
    async def test_fallback_synthesis_highest_risk_component(self):
        """Verify _synthesize_fallback_answer extracts maximum risk component and formats structured report."""
        async with MCPClient() as client:
            orchestrator = OrchestratorAgent(mcp_client=client)

            mock_component_risks = {
                "count": 3,
                "component_risks": [
                    {
                        "name": "Authentication",
                        "risk_score": 45.0,
                        "open_issues": 4,
                        "critical_high_issues": 4,
                        "reasons": [
                            "Contains 4 open Critical/High bugs (+45 pts)",
                            "Average open bug age is 18 days (+10 pts)"
                        ],
                        "metrics": {"open_bugs_count": 4, "open_critical_high_count": 4}
                    },
                    {
                        "name": "Database",
                        "risk_score": 25.0,
                        "open_issues": 1,
                        "critical_high_issues": 1,
                        "reasons": ["Contains 1 open Critical/High bugs (+15 pts)"],
                        "metrics": {"open_bugs_count": 1, "open_critical_high_count": 1}
                    },
                    {
                        "name": "Frontend",
                        "risk_score": 5.0,
                        "open_issues": 1,
                        "critical_high_issues": 0,
                        "reasons": ["Contains 1 open Medium/Low bugs (+5 pts)"],
                        "metrics": {"open_bugs_count": 1, "open_critical_high_count": 0}
                    }
                ]
            }

            observations = {"get_component_risk": mock_component_risks}
            answer = orchestrator._synthesize_fallback_answer("Which component has the highest risk?", observations)

            assert "# Component Risk & Hotspot Analysis" in answer
            assert "**Authentication**" in answer
            assert "45.0/100" in answer or "45/100" in answer
            assert "4 open issues" in answer
            assert "Investigate **Authentication** first" in answer
            assert "| Rank | Component | Risk Tier | Risk Score | Open Issues | Critical/High |" in answer
            assert "Database" in answer
            assert "Frontend" in answer
