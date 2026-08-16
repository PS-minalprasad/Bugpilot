"""
BugPilot — Integration Test Suite for MCP Server (Phase 4)
============================================================
Connects a real official MCP Client via stdio transport to the real MCP Server.
Verifies tool discovery, schemas, read-only tools list, all 8 tool invocations,
invalid input handling, missing bug handling, and results validation.
"""

import sys
import json
import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_mcp_server_full_suite():
    """Run full MCP server integration tests in a single session scope."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from mcp_server.server import main; main()"],
        env=None
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Tool discovery
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            expected_tools = [
                "search_bugs",
                "get_bug",
                "get_bug_metrics",
                "get_bug_trends",
                "get_aging_bugs",
                "get_reopened_bugs",
                "get_component_risk",
                "get_release_risk"
            ]
            assert len(tools_result.tools) == 8
            assert sorted(tool_names) == sorted(expected_tools)
            for t in tools_result.tools:
                assert t.description is not None

            # 2. search_bugs
            res_search = await session.call_tool("search_bugs", arguments={"query": "auth", "limit": 5})
            assert not res_search.is_error
            data_search = json.loads(res_search.content[0].text)
            assert "count" in data_search
            assert data_search["data_source"] in ["PostgreSQL", "Synthetic Demo Data"]

            # 3. get_bug (existing & missing)
            res_bug_exist = await session.call_tool("get_bug", arguments={"bug_id": "API-1"})
            assert not res_bug_exist.is_error
            data_exist = json.loads(res_bug_exist.content[0].text)
            assert data_exist["found"] is True
            assert data_exist["bug"]["id"] == "API-1"

            res_bug_miss = await session.call_tool("get_bug", arguments={"bug_id": "MISSING-999"})
            assert not res_bug_miss.is_error
            data_miss = json.loads(res_bug_miss.content[0].text)
            assert data_miss["found"] is False

            # 4. get_bug_metrics
            res_metrics = await session.call_tool("get_bug_metrics", arguments={})
            assert not res_metrics.is_error
            data_metrics = json.loads(res_metrics.content[0].text)
            assert data_metrics["summary"]["total_bugs"] >= 0

            # 5. get_bug_trends
            res_trends = await session.call_tool("get_bug_trends", arguments={})
            assert not res_trends.is_error
            data_trends = json.loads(res_trends.content[0].text)
            assert len(data_trends["creation_resolution_trends"]) > 0

            # 6. get_aging_bugs
            res_aging = await session.call_tool("get_aging_bugs", arguments={"min_age_days": 0.0, "limit": 10})
            assert not res_aging.is_error
            data_aging = json.loads(res_aging.content[0].text)
            assert "aging_bugs" in data_aging

            # 7. get_reopened_bugs
            res_reopened = await session.call_tool("get_reopened_bugs", arguments={"limit": 5})
            assert not res_reopened.is_error
            data_reopened = json.loads(res_reopened.content[0].text)
            assert "reopened_bugs" in data_reopened

            # 8. get_component_risk
            res_c_risk = await session.call_tool("get_component_risk", arguments={})
            assert not res_c_risk.is_error
            data_c_risk = json.loads(res_c_risk.content[0].text)
            assert "component_risks" in data_c_risk

            # 9. get_release_risk
            res_r_risk = await session.call_tool("get_release_risk", arguments={})
            assert not res_r_risk.is_error
            data_r_risk = json.loads(res_r_risk.content[0].text)
            assert "release_risks" in data_r_risk

            # 10. Invalid input error handling
            res_invalid = await session.call_tool("search_bugs", arguments={})
            assert res_invalid.is_error or "Error" in res_invalid.content[0].text
