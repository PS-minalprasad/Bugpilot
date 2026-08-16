"""
BugPilot — Sprint Model
========================
Pydantic v2 model for a system sprint.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class SprintStatus(str, Enum):
    """Sprint lifecycle states."""
    FUTURE = "future"
    ACTIVE = "active"
    CLOSED = "closed"


class Sprint(BaseModel):
    """
    A development sprint.

    Bugs reference sprints via ``Bug.sprint_id``.
    Populated by DataProvider (PostgresProvider or SyntheticProvider).
    """

    # Identity
    id: str = Field(..., description="Sprint identifier, e.g. SP-1")
    name: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(default="", max_length=1000, description="Sprint goal statement")

    # Lifecycle
    status: SprintStatus = SprintStatus.FUTURE
    start_date: datetime
    end_date: datetime

    # Metrics (aggregated in Phase 3 analytics)
    total_bugs: int = Field(default=0, ge=0)
    resolved_bugs: int = Field(default=0, ge=0)
    critical_bugs: int = Field(default=0, ge=0)

    # Board linkage
    board_id: Optional[str] = None
    team: str = Field(default="", description="Team name owning this sprint")

    # Data provenance
    data_source: str = Field(default="Synthetic Demo Data")

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_dates(self) -> "Sprint":
        if self.end_date <= self.start_date:
            raise ValueError(
                f"Sprint end_date ({self.end_date}) must be after start_date ({self.start_date})"
            )
        return self

    @model_validator(mode="after")
    def validate_bug_counts(self) -> "Sprint":
        if self.resolved_bugs > self.total_bugs:
            raise ValueError(
                f"resolved_bugs ({self.resolved_bugs}) cannot exceed total_bugs ({self.total_bugs})"
            )
        return self

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @property
    def duration_days(self) -> float:
        return (self.end_date - self.start_date).total_seconds() / 86400

    @property
    def resolution_rate(self) -> float:
        """Fraction of bugs resolved. Returns 0.0 if no bugs."""
        if self.total_bugs == 0:
            return 0.0
        return self.resolved_bugs / self.total_bugs

    model_config = {"use_enum_values": True}
