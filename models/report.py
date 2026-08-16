"""
BugPilot — Report Models
=========================
Pydantic v2 models for the final AnalysisReport and ReflectionResult.
These are the terminal outputs of the agent pipeline (Phases 8+).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ReportSection(BaseModel):
    """A single named section within an AnalysisReport."""
    title: str
    content: str = Field(..., description="Markdown-formatted content")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Agent's confidence in this section (0.0–1.0)",
    )
    is_empty: bool = False


class AnalysisReport(BaseModel):
    """
    Structured output from the Report Agent (Phase 8).

    Contains all sections of the final bug intelligence report.
    """

    report_id: str
    analysis_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    data_source: str = "Synthetic Demo Data"

    # Required sections
    executive_summary: ReportSection
    bug_analysis: ReportSection
    trend_analysis: ReportSection
    risk_assessment: ReportSection
    recommendations: ReportSection

    # Optional extras
    raw_insights: Dict[str, Any] = Field(
        default_factory=dict,
        description="Unstructured insights from sub-agents (debug reference)",
    )

    @property
    def all_sections(self) -> List[ReportSection]:
        return [
            self.executive_summary,
            self.bug_analysis,
            self.trend_analysis,
            self.risk_assessment,
            self.recommendations,
        ]

    @property
    def has_all_sections(self) -> bool:
        return all(not s.is_empty for s in self.all_sections)

    @property
    def average_confidence(self) -> float:
        scores = [s.confidence for s in self.all_sections]
        return round(sum(scores) / len(scores), 3) if scores else 0.0


class ReflectionResult(BaseModel):
    """
    Output from the Reflection Agent (Phase 8).

    Provides a self-critique of the AnalysisReport.
    """

    reflection_id: str
    report_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Quality score (0.0 = terrible, 1.0 = excellent)
    quality_score: float = Field(..., ge=0.0, le=1.0)

    # Identified gaps
    gaps: List[str] = Field(
        default_factory=list,
        description="Sections or data points the reflection agent flagged as weak or missing",
    )

    # Follow-up questions for the user
    follow_up_questions: List[str] = Field(default_factory=list)

    # Summary of critique
    critique: str = Field(
        default="",
        description="Natural language critique of the analysis report",
    )

    # Confidence in the reflection itself
    reflection_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("quality_score")
    @classmethod
    def score_precision(cls, v: float) -> float:
        return round(v, 3)

    @property
    def is_acceptable(self) -> bool:
        """Report passes reflection if quality_score >= 0.6."""
        return self.quality_score >= 0.6
