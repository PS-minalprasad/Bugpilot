"""
BugPilot — MCP Client Module (Phase 5)
=======================================
Provides a robust, async MCPClient that connects to the BugPilot MCP Server.
Implements dynamic tool discovery, schema parsing, tool allowlist filtering,
timeout guards, structured output formatting, and safe error handling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from backend.core.exceptions import (
    MCPConnectionError,
    MCPError,
    MCPToolExecutionError,
    MCPToolNotFoundError,
)

logger = logging.getLogger("bugpilot.mcp_client")

# Approved read-only tools allowlist
DEFAULT_ALLOWLIST = {
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
}


class DiscoveredToolInfo:
    """Dataclass holding dynamic metadata for a discovered MCP tool."""

    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def __repr__(self) -> str:
        return f"DiscoveredToolInfo(name={self.name!r})"


class MCPClient:
    """
    Client interface connecting to the BugPilot MCP Server.
    Uses stdio transport by default to launch and communicate with the server process.
    """

    def __init__(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        allowlist: Optional[set[str]] = None,
        default_timeout_seconds: float = 10.0,
    ) -> None:
        self.command = command or sys.executable
        self.args = args or ["-c", "from mcp_server.server import main; main()"]
        self.allowlist = allowlist if allowlist is not None else DEFAULT_ALLOWLIST
        self.timeout = default_timeout_seconds

        self._discovered_tools: Dict[str, DiscoveredToolInfo] = {}
        self._session: Optional[ClientSession] = None
        self._stdio_context = None
        self._session_context = None
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def discovered_tools(self) -> Dict[str, DiscoveredToolInfo]:
        """Returns map of allowed, dynamically discovered tools."""
        return self._discovered_tools

    async def connect(self) -> None:
        """
        Connect to the MCP server, initialize the session, and discover tools dynamically.
        """
        if self._is_connected:
            return

        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=None,
        )

        try:
            self._stdio_context = stdio_client(server_params)
            read, write = await asyncio.wait_for(
                self._stdio_context.__aenter__(), timeout=self.timeout
            )
            self._session_context = ClientSession(read, write)
            self._session = await asyncio.wait_for(
                self._session_context.__aenter__(), timeout=self.timeout
            )
            await asyncio.wait_for(self._session.initialize(), timeout=self.timeout)
            self._is_connected = True
            logger.info("Connected to MCP Server via stdio.")
        except Exception as err:
            await self._cleanup()
            logger.error(f"Failed to connect to MCP server: {err}")
            raise MCPConnectionError(f"Failed to connect to MCP server: {err}") from err

        # Perform dynamic tool discovery
        await self.discover_tools()

    async def discover_tools(self) -> List[DiscoveredToolInfo]:
        """
        Dynamically query list_tools() from server, inspect schemas, apply allowlist filter.
        """
        if not self._session or not self._is_connected:
            raise MCPConnectionError("Cannot discover tools: Client is not connected.")

        try:
            tools_result = await asyncio.wait_for(
                self._session.list_tools(), timeout=self.timeout
            )
        except Exception as err:
            logger.error(f"Failed to list tools from MCP server: {err}")
            raise MCPError(f"Failed to list tools: {err}") from err

        discovered = {}
        for tool in tools_result.tools:
            # Check allowlist
            if self.allowlist and tool.name not in self.allowlist:
                logger.warning(f"Tool '{tool.name}' omitted because it is not in the allowlist.")
                continue

            input_schema = (
                tool.inputSchema if hasattr(tool, "inputSchema") and tool.inputSchema else {}
            )
            tool_info = DiscoveredToolInfo(
                name=tool.name,
                description=tool.description or "",
                input_schema=input_schema if isinstance(input_schema, dict) else {},
            )
            discovered[tool.name] = tool_info

        self._discovered_tools = discovered
        logger.info(f"Discovered {len(discovered)} approved tools from MCP server.")
        return list(discovered.values())

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Invoke an MCP tool dynamically by name with arguments.
        """
        if not self._is_connected or not self._session:
            raise MCPConnectionError(f"Cannot call tool '{name}': Client is not connected.")

        if name not in self.allowlist:
            raise MCPToolNotFoundError(f"Tool '{name}' is not permitted by allowlist policy.")

        if name not in self._discovered_tools:
            # Refresh dynamic discovery once
            await self.discover_tools()
            if name not in self._discovered_tools:
                raise MCPToolNotFoundError(f"Tool '{name}' was not discovered on the MCP server.")

        args = arguments or {}
        call_timeout = timeout or self.timeout

        # Guardrail 5: Parameter safety - inspect string arguments for arbitrary SQL injection attempts
        for k, v in args.items():
            if isinstance(v, str):
                v_upper = v.upper()
                if any(sql_kw in v_upper for sql_kw in ["DROP TABLE", "TRUNCATE", "DELETE FROM", "ALTER TABLE", "INSERT INTO"]):
                    raise MCPToolExecutionError(f"Arbitrary SQL execution attempt detected in tool argument '{k}'. Access denied.")

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments=args),
                timeout=call_timeout,
            )
        except asyncio.TimeoutError as err:
            logger.error(f"Execution of tool '{name}' timed out after {call_timeout}s.")
            raise MCPToolExecutionError(f"Tool '{name}' timed out after {call_timeout}s.") from err
        except Exception as err:
            logger.error(f"MCP tool call '{name}' failed: {err}")
            raise MCPToolExecutionError(f"Tool '{name}' invocation failed: {err}") from err

        if result.is_error:
            error_msg = result.content[0].text if result.content else "Unknown tool error"
            logger.error(f"Tool '{name}' returned error: {error_msg}")
            raise MCPToolExecutionError(f"Tool '{name}' returned error: {error_msg}")

        # Parse text content into JSON if possible
        if result.content and hasattr(result.content[0], "text"):
            raw_text = result.content[0].text
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                return {"text": raw_text, "data_source": "Synthetic Demo Data"}

        return {}

    async def close(self) -> None:
        """Close the MCP session and process safely."""
        await self._cleanup()

    async def _cleanup(self) -> None:
        self._is_connected = False
        self._discovered_tools = {}
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._session_context = None
            self._session = None
        if self._stdio_context:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._stdio_context = None

    async def __aenter__(self) -> MCPClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
