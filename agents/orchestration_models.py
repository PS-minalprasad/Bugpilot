"""
BugPilot — Execution Step & Orchestrator Models (Phase 7)
==========================================================
Defines models for tracking step-by-step agentic loop execution metadata.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StepMetadata(BaseModel):
    """
    Metadata for a single step in the agentic reasoning loop.
    Exposes only non-internal fields (no chain-of-thought).
    """

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_number: int = Field(..., description="1-based step counter in loop")
    agent_name: str = Field(..., description="Specialist agent or orchestrator name")
    tool_name: str = Field(..., description="MCP Tool invoked during step")
    intent: Optional[str] = Field(default=None, description="Query intent identified for step")
    status: str = Field(default="success", description="Status of tool execution")
    result_summary: str = Field(..., description="High level summary of observation result")
    duration_seconds: float = Field(..., description="Time taken for this step")


class OrchestrationResult(BaseModel):
    """Structured response from Orchestrator Agent execution."""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_query: str = Field(..., description="Original user prompt")
    intent: Optional[str] = Field(default=None, description="Classified query intent")
    status: str = Field(default="success", description="Overall execution status")
    final_answer: str = Field(..., description="Consolidated answer synthesized from observations")
    total_steps: int = Field(..., description="Total reasoning loop steps executed")
    execution_steps: List[StepMetadata] = Field(
        default_factory=list, description="Step metadata log (no CoT exposed)"
    )
    elapsed_seconds: float = Field(..., description="Total execution wall-clock time")
    error: Optional[str] = Field(default=None, description="Error details if execution failed")
