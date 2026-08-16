"""
BugPilot — Agent Models & Base Definitions (Phase 6)
=====================================================
Defines base interfaces, state models, and execution schemas for specialist agents.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from mcp_client.client import MCPClient


class AgentExecutionStatus(str):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AgentResult(BaseModel):
    """Structured output returned by specialist agents."""

    agent_name: str = Field(..., description="Name of the specialist agent")
    task: str = Field(..., description="The task/query processed by the agent")
    status: str = Field(default="success", description="Execution status")
    findings: str = Field(..., description="Human-readable synthesis/findings")
    tools_used: List[str] = Field(default_factory=list, description="MCP tools invoked during execution")
    supporting_evidence: Dict[str, Any] = Field(
        default_factory=dict, description="Raw numerical & structured data retrieved from MCP tools"
    )
    elapsed_seconds: float = Field(default=0.0, description="Execution time in seconds")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")


class BaseAgent(ABC):
    """
    Abstract base class for all specialist agents.
    Enforces MCPClient usage for all data queries.
    """

    def __init__(
        self,
        name: str,
        mcp_client: MCPClient,
        max_iterations: int = 5,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.name = name
        self.mcp_client = mcp_client
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def run(self, task: str, **kwargs: Any) -> AgentResult:
        """
        Execute the agent's reasoning loop for the given task.
        """
        pass
