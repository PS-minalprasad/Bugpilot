"""
BugPilot — Orchestrator Agent Unit & Integration Test Suite (Phase 7)
=====================================================================
Verifies real agentic loop orchestration:
  - Single-step requests
  - Multi-step requests (dynamic 1st tool -> observation -> 2nd tool -> observation -> 3rd tool -> finish)
  - Maximum iteration limits
  - Timeout handling
  - MCP failure handling
  - Exposing only clean step metadata (no Chain of Thought)
Communicates over real stdio MCP transport against real MCP server.
"""

import sys
import pytest

from agents import OrchestratorAgent
from mcp_client import MCPClient
from backend.core.exceptions import (
    AgentError,
    AgentExecutionError,
    AgentTimeoutError,
    MCPConnectionError,
    ValidationError,
)


class TestOrchestratorAgentIntegration:
    """Integration test suite for OrchestratorAgent with real MCP Server/Client."""

    @pytest.mark.asyncio
    async def test_single_step_request(self):
        """Verify single-step query resolves in 1 step."""
        async with MCPClient() as client:
            orchestrator = OrchestratorAgent(client)
            result = await orchestrator.run("Show total bug metrics count")

            assert result.status == "success"
            assert result.total_steps == 1
            assert len(result.execution_steps) == 1

            step1 = result.execution_steps[0]
            assert step1.step_number == 1
            assert step1.agent_name == "Bug Analyst"
            assert step1.tool_name == "get_bug_metrics"
            assert step1.status == "success"
            assert isinstance(step1.execution_id, str)
            assert isinstance(step1.duration_seconds, float)

            # Ensure no chain of thought attribute exists on step metadata
            assert not hasattr(step1, "chain_of_thought")
            assert not hasattr(step1, "reasoning")

            assert "Total" in result.final_answer or "bugs" in result.final_answer.lower()

    @pytest.mark.asyncio
    async def test_multi_step_request_observation_loop(self):
        """
        Prove real multi-step agentic loop:
          Step 1: get_bug_metrics -> Observation 1
          Step 2: get_component_risk -> Observation 2
          Step 3: get_bug_trends -> Observation 3 -> Finish
        """
        async with MCPClient() as client:
            orchestrator = OrchestratorAgent(client)
            result = await orchestrator.run(
                "Analyze overall bug metrics, component risk profiles, and historical trends"
            )

            assert result.status == "success"
            assert result.total_steps >= 3
            assert len(result.execution_steps) >= 3

            # Step 1
            s1 = result.execution_steps[0]
            assert s1.tool_name == "get_bug_metrics"
            assert s1.agent_name == "Bug Analyst"

            # Step 2
            s2 = result.execution_steps[1]
            assert s2.tool_name == "get_component_risk"
            assert s2.agent_name == "Risk Analyst"

            # Step 3
            s3 = result.execution_steps[2]
            assert s3.tool_name == "get_bug_trends"
            assert s3.agent_name == "Trend Analyst"

            # Verify final answer incorporates data from all observations
            assert "Bug Summary" in result.final_answer
            assert "Component Risk" in result.final_answer
            assert "Trend Analysis" in result.final_answer

    @pytest.mark.asyncio
    async def test_maximum_iterations_limit(self):
        """Verify orchestrator respects max_iterations cap."""
        async with MCPClient() as client:
            # Force max_iterations = 2 on a request that would want 3 steps
            orchestrator = OrchestratorAgent(client, max_iterations=2)
            result = await orchestrator.run(
                "Analyze overall bug metrics, component risk profiles, and historical trends"
            )

            assert result.status == "success"
            assert result.total_steps == 2
            assert len(result.execution_steps) == 2

    @pytest.mark.asyncio
    async def test_input_validation(self):
        """Verify empty input raises ValidationError."""
        async with MCPClient() as client:
            orchestrator = OrchestratorAgent(client)
            with pytest.raises(ValidationError) as exc_info:
                await orchestrator.run("   ")
            assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_mcp_failure_handling(self):
        """Verify orchestrator handles MCP connection failures gracefully."""
        client = MCPClient(command="non_existent_binary")
        orchestrator = OrchestratorAgent(client)
        with pytest.raises((AgentExecutionError, MCPConnectionError)):
            await orchestrator.run("Analyze bug metrics and risk")

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Verify orchestrator enforces execution timeout."""
        async with MCPClient() as client:
            orchestrator = OrchestratorAgent(client, timeout_seconds=0.000001)
            with pytest.raises(AgentTimeoutError) as exc_info:
                await orchestrator.run("Analyze bug metrics")
            assert "timed out" in str(exc_info.value).lower()
