"""
BugPilot — Analysis Request / Response Models
==============================================
Pydantic v2 models for the analysis pipeline API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    """Lifecycle of an analysis run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Completed with some agent errors


class AnalysisScope(str, Enum):
    """What the analysis should cover."""
    FULL = "full"           # Bug + Trend + Risk
    BUGS_ONLY = "bugs"
    TRENDS_ONLY = "trends"
    RISK_ONLY = "risk"


class AnalysisRequest(BaseModel):
    """
    Request payload for ``POST /api/analyze``.

    Submitted by the React frontend or API consumer.
    """

    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural language question or analysis prompt",
        examples=["What are the top critical bugs this sprint?"],
    )
    scope: AnalysisScope = Field(
        default=AnalysisScope.FULL,
        description="Which aspects to analyse",
    )
    sprint_id: Optional[str] = Field(
        default=None,
        description="Limit analysis to a specific sprint. None = all sprints.",
    )
    component: Optional[str] = Field(
        default=None,
        description="Limit analysis to a specific component. None = all components.",
    )
    max_bugs: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of bugs to include in analysis",
    )


class AgentResultSummary(BaseModel):
    """Summary of a single agent's contribution."""
    agent_name: str
    status: AnalysisStatus
    elapsed_ms: float = 0.0
    insight_count: int = 0
    error: Optional[str] = None


class AnalysisMetadata(BaseModel):
    """Metadata attached to every analysis response."""
    analysis_id: str
    request_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    elapsed_ms: float = 0.0
    data_source: str = "Synthetic Demo Data"
    agent_results: List[AgentResultSummary] = Field(default_factory=list)
    status: AnalysisStatus = AnalysisStatus.PENDING
