"""
BugPilot — Integration Test Suite for MCPClient (Phase 5)
=========================================================
Tests the MCPClient connecting to a real MCP Server.
Verifies:
  - Connection & session initialization
  - Dynamic tool discovery & schema reading
  - Tool invocations (get_bug, get_bug_metrics, component_risk)
  - Invalid tool handling & allowlist filtering
  - Connection failure & timeout handling
"""

import sys
import pytest

from mcp_client.client import MCPClient, DiscoveredToolInfo
from backend.core.exceptions import (
    MCPConnectionError,
    MCPToolExecutionError,
    MCPToolNotFoundError,
)


class TestMCPClientIntegration:
    """Integration test suite for MCPClient using real MCP server process."""

    @pytest.mark.asyncio
    async def test_client_connect_and_dynamic_discovery(self):
        """Verify connection, session initialization, and dynamic tool discovery."""
        async with MCPClient() as client:
            assert client.is_connected is True

            tools = client.discovered_tools
            assert len(tools) >= 8

            expected_tools = [
                "search_bugs",
                "get_bug",
                "get_bug_metrics",
                "get_bug_trends",
                "get_aging_bugs",
                "get_reopened_bugs",
                "get_component_risk",
                "get_release_risk",
                "get_bug_history",
                "get_related_bugs",
            ]
            for tool_name in expected_tools:
                assert tool_name in tools
                info = tools[tool_name]
                assert isinstance(info, DiscoveredToolInfo)
                assert info.name == tool_name
                assert isinstance(info.description, str)
                assert len(info.description) > 0
                assert isinstance(info.input_schema, dict)

    @pytest.mark.asyncio
    async def test_get_bug_invocation(self):
        """Test get_bug invocation through MCPClient."""
        from backend.database.repository import db_create_issue, db_get_issue_by_id_or_key
        if not db_get_issue_by_id_or_key("API-1", org_id="org-acme"):
            db_create_issue(
                org_id="org-acme",
                data={
                    "id": "API-1",
                    "issue_key": "API-1",
                    "title": "API Spec Issue",
                    "description": "Test issue",
                    "status": "Open",
                    "priority": "High",
                    "severity": "High",
                    "project": "BugPilot",
                    "component": "API",
                },
            )
        async with MCPClient() as client:
            res = await client.call_tool("get_bug", {"bug_id": "API-1", "org_id": "org-acme"})
            assert isinstance(res, dict)
            assert res.get("found") is True
            assert res.get("bug", {}).get("id") == "API-1"
            assert res.get("data_source") in ["SQLite", "PostgreSQL", "Synthetic Demo Data"]

            # Missing bug
            res_missing = await client.call_tool("get_bug", {"bug_id": "NOTFOUND-999", "org_id": "org-acme"})
            assert isinstance(res_missing, dict)
            assert res_missing.get("found") is False
            assert "not found" in res_missing.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_get_bug_metrics_invocation(self):
        """Test get_bug_metrics invocation through MCPClient."""
        async with MCPClient() as client:
            res = await client.call_tool("get_bug_metrics", {"org_id": "org-acme"})
            assert isinstance(res, dict)
            summary = res.get("summary", {})
            assert summary.get("total_bugs") >= 0
            assert summary.get("data_source") in ["SQLite", "PostgreSQL", "Synthetic Demo Data"]
            assert res.get("data_source") in ["SQLite", "PostgreSQL", "Synthetic Demo Data"]

    @pytest.mark.asyncio
    async def test_get_component_risk_invocation(self):
        """Test get_component_risk invocation through MCPClient."""
        async with MCPClient() as client:
            res = await client.call_tool("get_component_risk", {})
            assert isinstance(res, dict)
            assert "component_risks" in res
            assert res.get("count", 0) > 0
            assert res.get("data_source") in ["SQLite", "PostgreSQL", "Synthetic Demo Data"]

    @pytest.mark.asyncio
    async def test_invalid_tool_handling(self):
        """Test calling a tool not present on server raises MCPToolNotFoundError."""
        async with MCPClient() as client:
            with pytest.raises(MCPToolNotFoundError) as exc_info:
                await client.call_tool("non_existent_tool", {})
            assert "non_existent_tool" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_read_only_allowlist_filtering(self):
        """Test allowlist policy filtering."""
        restricted_allowlist = {"get_bug", "get_bug_metrics"}
        async with MCPClient(allowlist=restricted_allowlist) as client:
            # Only allowed tools in discovered map
            assert set(client.discovered_tools.keys()) == restricted_allowlist

            # Allowed invocation works
            res = await client.call_tool("get_bug", {"bug_id": "API-1"})
            assert res.get("found") is True

            # Disallowed tool invocation fails with policy error
            with pytest.raises(MCPToolNotFoundError) as exc_info:
                await client.call_tool("search_bugs", {"query": "auth"})
            assert "allowlist" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self):
        """Test client raises MCPConnectionError when connecting to an invalid binary command."""
        client = MCPClient(command="non_existent_python_binary_path_xyz")
        with pytest.raises(MCPConnectionError) as exc_info:
            await client.connect()
        assert "failed to connect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout guard during tool execution."""
        async with MCPClient(default_timeout_seconds=10.0) as client:
            # Extremely short timeout to force timeout
            with pytest.raises(MCPToolExecutionError) as exc_info:
                await client.call_tool("get_bug_metrics", {}, timeout=0.000001)
            assert "timed out" in str(exc_info.value).lower()
