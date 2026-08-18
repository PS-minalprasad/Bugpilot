"""
BugPilot — Analytics Output Models
===================================
Pydantic v2 models representing the structured outputs of the AnalyticsService.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SummaryMetrics(BaseModel):
    """Overall summary metrics for the analyzed dataset."""
    total_bugs: int = Field(..., ge=0)
    open_bugs: int = Field(..., ge=0)
    resolved_bugs: int = Field(..., ge=0)
    critical_high_bugs: int = Field(..., ge=0, description="Total open critical or high severity bugs")
    reopened_bugs: int = Field(..., ge=0, description="Total bugs that have been reopened")
    reopen_rate: float = Field(..., ge=0.0, le=1.0, description="Fraction of total bugs that were reopened")
    average_resolution_time_days: float = Field(..., ge=0.0, description="Mean time to resolve resolved bugs")
    data_source: str = "SQLite"


class BreakdownMetrics(BaseModel):
    """Categorized bug counts."""
    by_component: Dict[str, int] = Field(default_factory=dict)
    by_priority: Dict[str, int] = Field(default_factory=dict)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)


class TrendPoint(BaseModel):
    """Data point for time-series charts (sprints, monthly, etc.)."""
    period: str = Field(..., description="Name of the period, e.g. 'Sprint 1' or '2026-08'")
    created: int = Field(default=0, ge=0)
    resolved: int = Field(default=0, ge=0)


class AgingBugInfo(BaseModel):
    """Details of an unresolved bug and its age."""
    bug_id: str
    summary: str
    severity: str
    priority: str
    component: str
    age_days: float = Field(..., ge=0.0)
    status: str


class RiskMetric(BaseModel):
    """Deterministic, explainable risk score for components or releases."""
    name: str = Field(..., description="Name of the component or release version")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk score between 0.0 and 100.0")
    open_issues: int = Field(default=0, ge=0, description="Total open bugs in this component or release")
    critical_high_issues: int = Field(default=0, ge=0, description="Total critical/high open bugs")
    reasons: List[str] = Field(default_factory=list, description="Reasoning or factors behind the score")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Raw underlying metrics used in formula")


class AnalyticsPayload(BaseModel):
    """Consolidated response payload from the AnalyticsService."""
    summary: SummaryMetrics
    breakdowns: BreakdownMetrics
    creation_resolution_trends: List[TrendPoint] = Field(default_factory=list)
    sprint_trends: List[TrendPoint] = Field(default_factory=list)
    aging_bugs: List[AgingBugInfo] = Field(default_factory=list)
    component_risks: List[RiskMetric] = Field(default_factory=list)
    release_risks: List[RiskMetric] = Field(default_factory=list)
    data_source: str = "SQLite"
