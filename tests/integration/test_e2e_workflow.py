"""
BugPilot — Comprehensive End-to-End (E2E) Test Suite (Phase 12)
===============================================================
Tests the full system stack with real components:
React Frontend (Contract via API) -> FastAPI -> Orchestrator -> Specialized Agents
-> MCP Client -> MCP Server -> MCP Tools -> Analytics Service -> Synthetic Demo Data
-> Report Agent -> Reflection Agent -> Final Response.

Verifies 15 Critical Scenarios:
1. Application Health
2. MCP Server Startup & Lifecycle
3. Dynamic MCP Tool Discovery
4. Single-step Chat Execution
5. Multi-step Agentic Chat Execution
6. Bug Analysis Workflow
7. Trend Analysis Workflow
8. Risk Analysis Workflow
9. Reflection Agent CONFIRM
10. Reflection Agent CORRECT
11. Invalid Request & Error Handling
12. MCP Failure & Disconnection Handling
13. Timeout Guard Handling
14. Frontend -> Backend Chat Schema Contract
15. Complete User Journey Flow
"""

import pytest
import httpx
from typing import Any, Dict

from backend.main import app
from mcp_client import MCPClient
from agents import OrchestratorAgent, ReportAgent, ReflectionAgent
from agents.reporting import ReflectionEvaluation
from backend.core.exceptions import MCPConnectionError, MCPToolExecutionError


@pytest.fixture
async def e2e_api_client():
    """ASGI TestClient fixture for FastAPI application."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


class TestE2ECompleteWorkflow:
    """E2E Test Suite verifying all 15 Phase 12 requirements."""

    # -------------------------------------------------------------------------
    # 1. Application Health & Readiness
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_01_application_health(self, e2e_api_client: httpx.AsyncClient):
        """Scenario 1: Verify application health endpoints and configuration."""
        res = await e2e_api_client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["app"] == "BugPilot"
        assert data["data_source"] in ["SQLite", "PostgreSQL"]

    # -------------------------------------------------------------------------
    # 2. MCP Server Startup
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_02_mcp_server_startup(self):
        """Scenario 2: Verify real MCP server process boots and establishes stdio channel."""
        client = MCPClient()
        assert client.is_connected is False
        await client.connect()
        assert client.is_connected is True
        await client.close()
        assert client.is_connected is False

    # -------------------------------------------------------------------------
    # 3. Dynamic Tool Discovery
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_03_mcp_tool_discovery(self):
        """Scenario 3: Verify dynamic tool discovery via MCPClient list_tools()."""
        async with MCPClient() as client:
            tools = client.discovered_tools
            assert len(tools) == 8
            assert "search_bugs" in tools
            assert "get_bug_metrics" in tools
            assert "get_component_risk" in tools
            for t_name, t_info in tools.items():
                assert t_info.name == t_name
                assert len(t_info.description) > 0
                assert isinstance(t_info.input_schema, dict)

    # -------------------------------------------------------------------------
    # 4. Single-step Chat Workflow
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_04_single_step_chat(self, e2e_api_client: httpx.AsyncClient):
        """Scenario 4: Verify single-step chat execution through API -> Orchestrator -> MCP."""
        payload = {"message": "How many total bugs exist in the system?"}
        res = await e2e_api_client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert len(data["answer"]) > 0
        assert "Bug Analyst" in data["agents_used"]
        assert "get_bug_metrics" in data["tools_used"]
        assert data["reflection"]["verdict"] in ["CONFIRM", "CORRECT"]

    # -------------------------------------------------------------------------
    # 5. Multi-step Agentic Chat Execution
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_05_multi_step_agentic_chat(self):
        """Scenario 5: Verify real multi-step Orchestrator reasoning loop."""
        async with MCPClient() as client:
            orchestrator = OrchestratorAgent(mcp_client=client)
            query = "What is the highest risk component and how many open bugs does it have?"
            orc_res = await orchestrator.run(query)
            
            assert len(orc_res.execution_steps) >= 2
            tools_used = [step.tool_name for step in orc_res.execution_steps]
            assert "get_component_risk" in tools_used
            assert ("search_bugs" in tools_used or "get_bug_metrics" in tools_used)

    # -------------------------------------------------------------------------
    # 6. Specialist: Bug Analyst Workflow
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_06_bug_analysis_workflow(self, e2e_api_client: httpx.AsyncClient):
        """Scenario 6: Bug analysis workflow for unresolved and critical bugs."""
        payload = {"message": "Show critical unresolved bugs."}
        res = await e2e_api_client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "Bug Analyst" in data["agents_used"]
        assert "search_bugs" in data["tools_used"] or "get_bug_metrics" in data["tools_used"]

    # -------------------------------------------------------------------------
    # 7. Specialist: Trend Analyst Workflow
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_07_trend_analysis_workflow(self, e2e_api_client: httpx.AsyncClient):
        """Scenario 7: Trend analysis workflow for creation vs resolution velocity."""
        payload = {"message": "What is the current bug resolution trend?"}
        res = await e2e_api_client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "Trend Analyst" in data["agents_used"]
        assert "get_bug_trends" in data["tools_used"]

    # -------------------------------------------------------------------------
    # 8. Specialist: Risk Analyst Workflow
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_08_risk_analysis_workflow(self, e2e_api_client: httpx.AsyncClient):
        """Scenario 8: Risk analysis workflow for component risk and aging bugs."""
        payload = {"message": "Which component is highest risk?"}
        res = await e2e_api_client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "Risk Analyst" in data["agents_used"]
        assert "get_component_risk" in data["tools_used"]

    # -------------------------------------------------------------------------
    # 9. Reflection Agent: CONFIRM Verification
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_09_reflection_confirm(self):
        """Scenario 9: Reflection Agent returns CONFIRM for accurate metrics claims."""
        async with MCPClient() as client:
            metrics_res = await client.call_tool("get_bug_metrics", {})
            summary = metrics_res.get("summary", {})
            total = summary.get("total_bugs", 1000)
            open_cnt = summary.get("open_bugs", 39)
            
            accurate_answer = (
                f"The repository currently contains {total} total bugs, with {open_cnt} open bugs. "
                "Synthetic Demo Data."
            )
            reflection = ReflectionAgent()
            eval_res, _ = reflection.reflect(accurate_answer, {"summary": summary})
            assert eval_res.verdict == "CONFIRM"
            assert eval_res.quality_score >= 0.8
            assert len(eval_res.gaps) == 0

    # -------------------------------------------------------------------------
    # 10. Reflection Agent: CORRECT Verification
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_10_reflection_correct(self):
        """Scenario 10: Reflection Agent returns CORRECT for hallucinated or conflicting claims."""
        async with MCPClient() as client:
            metrics_res = await client.call_tool("get_bug_metrics", {"org_id": "org-acme"})
            evidence = {"summary": metrics_res.get("summary", {})}
            
            flawed_answer = "The system has 99999 total bugs and 0 open bugs."
            reflection = ReflectionAgent()
            eval_res, _ = reflection.reflect(flawed_answer, evidence)
            assert eval_res.verdict == "CORRECT"
            assert eval_res.corrected_answer is not None
            assert len(eval_res.corrected_answer) > 0

    # -------------------------------------------------------------------------
    # 11. Invalid Requests & Schema Validation
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_11_invalid_requests(self, e2e_api_client: httpx.AsyncClient):
        """Scenario 11: Verify API handles empty messages and malformed JSON payloads."""
        res_empty = await e2e_api_client.post("/api/v1/chat", json={"message": "   "})
        assert res_empty.status_code == 400

        res_invalid = await e2e_api_client.post("/api/v1/chat", json={"wrong_field": 123})
        assert res_invalid.status_code == 422

    # -------------------------------------------------------------------------
    # 12. MCP Failure & Disconnection Handling
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_12_mcp_failure_handling(self):
        """Scenario 12: Verify system handles disconnected or invalid MCP server gracefully."""
        client = MCPClient(command="non_existent_command_xyz")
        with pytest.raises(MCPConnectionError):
            await client.connect()

    # -------------------------------------------------------------------------
    # 13. Timeout Handling
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_13_timeout_handling(self):
        """Scenario 13: Verify execution timeout handling across MCP tools."""
        async with MCPClient() as client:
            with pytest.raises(MCPToolExecutionError) as exc:
                await client.call_tool("get_bug_metrics", {}, timeout=0.000001)
            assert "timed out" in str(exc.value).lower()

    # -------------------------------------------------------------------------
    # 14. Frontend -> Backend Chat Schema Contract
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_14_frontend_backend_schema_contract(self, e2e_api_client: httpx.AsyncClient):
        """Scenario 14: Verify response payload matches exact TypeScript API contract."""
        payload = {"message": "Which bugs have been reopened?"}
        res = await e2e_api_client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        
        # Verify fields required by React UI
        required_fields = [
            "execution_id",
            "request_id",
            "answer",
            "agents_used",
            "tools_used",
            "metrics",
            "reflection",
            "data_source",
            "elapsed_seconds",
        ]
        for field in required_fields:
            assert field in data
        assert isinstance(data["agents_used"], list)
        assert isinstance(data["tools_used"], list)
        assert isinstance(data["reflection"], dict)
        assert data["data_source"] in ["PostgreSQL", "Synthetic Demo Data"]

    # -------------------------------------------------------------------------
    # 15. Complete User Journey
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_e2e_15_complete_user_journey(self, e2e_api_client: httpx.AsyncClient):
        """Scenario 15: Complete end-to-end user journey producing a comprehensive engineering report."""
        payload = {"message": "Give me a complete engineering health report."}
        res = await e2e_api_client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        
        answer = data["answer"]
        assert "Engineering Bug Intelligence Report" in answer or "Summary" in answer
        assert data["data_source"] in ["PostgreSQL", "Synthetic Demo Data"]
        assert len(data["agents_used"]) >= 1
        assert len(data["tools_used"]) >= 1
        assert data["reflection"]["verdict"] in ["CONFIRM", "CORRECT"]
