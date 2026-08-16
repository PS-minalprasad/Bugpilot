"""
BugPilot — MCP Server Module Export (Phase 4)
==============================================
Exposes the MCP server application and helper tools.
"""

from mcp_server.server import app, main

__all__ = ["app", "main"]
