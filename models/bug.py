"""
BugPilot — Bug Model
=====================
Pydantic v2 model representing a system bug record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class BugSeverity(str, Enum):
    """Bug severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugPriority(str, Enum):
    """Bug priority levels."""
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class BugStatus(str, Enum):
    """Bug workflow statuses."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"
    WONT_FIX = "wont_fix"
    DUPLICATE = "duplicate"


class Bug(BaseModel):
    """
    A single bug / issue record.

    Provider-agnostic issue domain model.
    Populated from PostgreSQL/SQLite database or synthetic data.
    """

    # Identity
    id: str = Field(..., description="Unique bug identifier, e.g. BP-001")
    key: str = Field(default="", description="Issue key, e.g. BP-001")
    project: str = Field(default="", description="Project key, e.g. BP")
    issue_type: str = Field(default="Bug", description="Issue type, e.g. Bug")
    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(default="", description="Summary of the issue")
    description: str = Field(default="", max_length=5000)

    # Classification & Environment
    severity: BugSeverity
    priority: BugPriority = BugPriority.MEDIUM
    status: BugStatus = BugStatus.OPEN
    resolution: Optional[str] = Field(default=None, description="Resolution status, e.g. Fixed, Won't Fix, Duplicate")
    environment: Optional[str] = Field(default="production", description="Environment e.g. production, staging, development")
    affected_version: Optional[str] = Field(default=None, description="Affected release version")
    fix_version: Optional[str] = Field(default=None, description="Fix version release")

    # Deep Evidence & Investigation Context
    root_cause: Optional[str] = Field(default=None, description="Identified root cause analysis")
    business_impact: Optional[str] = Field(default=None, description="Business impact assessment")
    steps_to_reproduce: Optional[str] = Field(default=None, description="Steps to reproduce the bug")
    expected_behavior: Optional[str] = Field(default=None, description="Expected system behavior")
    actual_behavior: Optional[str] = Field(default=None, description="Actual observed behavior")
    comments: List[Dict[str, Any]] = Field(default_factory=list, description="List of discussion/investigation comments")
    linked_issue_ids: List[str] = Field(default_factory=list, description="IDs of linked or related bugs/issues")

    # Organisation
    component: str = Field(..., description="System component or service name")
    labels: List[str] = Field(default_factory=list)

    # Assignment
    reporter: str = Field(..., description="Username of the reporter")
    assignee: Optional[str] = Field(default=None, description="Username of the assignee")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    # Sprint linkage (populated in Phase 2)
    sprint_id: Optional[str] = None
    sprint: Optional[str] = Field(default=None, description="Sprint name or ID")
    reopened_count: int = Field(default=0, ge=0, description="Number of times the bug was reopened")

    # Data provenance — MUST be set by the provider
    data_source: str = Field(
        default="Synthetic Demo Data",
        description="Data origin label. Always 'Synthetic Demo Data' in this build.",
    )

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Bug ID must not be blank")
        return v.strip().upper()

    @field_validator("resolved_at")
    @classmethod
    def validate_resolved_at(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """resolved_at must be after created_at when set."""
        return v

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Synchronize id and key
            if "id" in data and not data.get("key"):
                data["key"] = data["id"]
            elif "key" in data and not data.get("id"):
                data["id"] = data["key"]
            
            # Synchronize title and summary
            if "title" in data and not data.get("summary"):
                data["summary"] = data["title"]
            elif "summary" in data and not data.get("title"):
                data["title"] = data["summary"]
                
            # Default project
            if not data.get("project") and "id" in data:
                parts = data["id"].split("-")
                data["project"] = parts[0] if parts else "BUGPILOT"
            
            # Synchronize sprint and sprint_id
            if "sprint_id" in data and not data.get("sprint"):
                data["sprint"] = data["sprint_id"]
            elif "sprint" in data and not data.get("sprint_id"):
                data["sprint_id"] = data["sprint"]
        return data

    # -------------------------------------------------------------------------
    # Computed helpers
    # -------------------------------------------------------------------------
    @property
    def is_open(self) -> bool:
        return self.status in {BugStatus.OPEN, BugStatus.IN_PROGRESS, BugStatus.IN_REVIEW}

    @property
    def is_resolved(self) -> bool:
        return self.status in {BugStatus.RESOLVED, BugStatus.CLOSED}

    @property
    def age_days(self) -> float:
        """Days since the bug was created (relative to now)."""
        return (datetime.utcnow() - self.created_at).total_seconds() / 86400

    model_config = {"use_enum_values": True}
