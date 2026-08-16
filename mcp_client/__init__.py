"""
BugPilot — MCP Client Package Export (Phase 5)
==============================================
Exposes MCPClient and related dataclasses/constants.
"""

from mcp_client.client import MCPClient, DiscoveredToolInfo, DEFAULT_ALLOWLIST

__all__ = ["MCPClient", "DiscoveredToolInfo", "DEFAULT_ALLOWLIST"]
