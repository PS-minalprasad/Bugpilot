"""
BugPilot — Specialist Agents Unit & Integration Test Suite (Phase 6)
=====================================================================
Verifies execution of BugAnalystAgent, TrendAnalystAgent, and RiskAnalystAgent
communicating over real MCPClient -> MCP Server -> MCP Tools -> Synthetic Data.
Tests correct tool selection, real evidence structure, input validation,
MCP connection failure, and timeout/error handling.
"""

import sys
import pytest

from agents import BugAnalystAgent, TrendAnalystAgent, RiskAnalystAgent
from mcp_client import MCPClient
from backend.core.exceptions import (
    AgentError,
    AgentExecutionError,
    AgentTimeoutError,
    MCPConnectionError,
    ValidationError,
)


class TestSpecialistAgentsIntegration:
    """Integration tests executing specialist agents against real MCP client/server."""

    @pytest.mark.asyncio
    async def test_bug_analyst_agent_execution(self):
        """Verify BugAnalystAgent executes over MCP and retrieves real bug metrics."""
        async with MCPClient() as client:
            agent = BugAnalystAgent(client)
            result = await agent.run("Analyze critical and open bug distribution")

            assert result.agent_name == "Bug Analyst"
            assert result.status == "success"
            assert "get_bug_metrics" in result.tools_used
            assert "get_reopened_bugs" in result.tools_used

            # Verify supporting evidence has real data from MCP
            metrics_summary = result.supporting_evidence.get("metrics", {}).get("summary", {})
            assert metrics_summary.get("total_bugs") >= 0
            assert metrics_summary.get("open_bugs") >= 0
            assert metrics_summary.get("data_source") in ["SQLite", "PostgreSQL", "Synthetic Demo Data"]
            assert "Total Bugs analyzed:" in result.findings

    @pytest.mark.asyncio
    async def test_trend_analyst_agent_execution(self):
        """Verify TrendAnalystAgent executes over MCP and retrieves trend points."""
        async with MCPClient() as client:
            agent = TrendAnalystAgent(client)
            result = await agent.run("Analyze monthly bug creation and resolution velocity")

            assert result.agent_name == "Trend Analyst"
            assert result.status == "success"
            assert "get_bug_trends" in result.tools_used

            trends_data = result.supporting_evidence.get("trends", {})
            assert "creation_resolution_trends" in trends_data
            assert "sprint_trends" in trends_data
            assert len(trends_data["creation_resolution_trends"]) > 0

    @pytest.mark.asyncio
    async def test_risk_analyst_agent_execution(self):
        """Verify RiskAnalystAgent executes over MCP and computes risk scores."""
        async with MCPClient() as client:
            agent = RiskAnalystAgent(client)
            result = await agent.run("Assess component and release risk profiles")

            assert result.agent_name == "Risk Analyst"
            assert result.status == "success"
            assert "get_component_risk" in result.tools_used
            assert "get_release_risk" in result.tools_used

            comp_risk = result.supporting_evidence.get("component_risk", {}).get("component_risks", [])
            assert len(comp_risk) > 0
            assert "risk_score" in comp_risk[0]

    @pytest.mark.asyncio
    async def test_agent_input_validation(self):
        """Verify agent raises ValidationError for empty prompt."""
        async with MCPClient() as client:
            agent = BugAnalystAgent(client)
            with pytest.raises(ValidationError) as exc_info:
                await agent.run("   ")
            assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_mcp_failure_handling(self):
        """Verify agent handles MCP connection/tool failure gracefully."""
        # Unconnected client with non-existent binary
        client = MCPClient(command="non_existent_binary")
        agent = BugAnalystAgent(client)
        with pytest.raises((AgentExecutionError, MCPConnectionError)) as exc_info:
            await agent.run("Analyze bugs")

    @pytest.mark.asyncio
    async def test_agent_timeout_handling(self):
        """Verify agent enforces timeout limit."""
        async with MCPClient() as client:
            agent = BugAnalystAgent(client, timeout_seconds=0.000001)
            with pytest.raises(AgentTimeoutError) as exc_info:
                await agent.run("Analyze bugs")
            assert "timed out" in str(exc_info.value).lower()
