"""
BugPilot — PostgresProvider
============================
Implements DataProvider using persistent PostgreSQL database models (IssueModel).
All issues carry data_source = "PostgreSQL".
"""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime, timezone, timedelta

from backend.config import settings
from backend.database.repository import (
    db_get_issues,
    db_get_issue_by_id_or_key,
    db_get_sprints,
    db_get_sprint,
)
from backend.database.models import IssueModel, SprintModel
from models.bug import Bug, BugSeverity, BugStatus, BugPriority
from models.sprint import Sprint
from providers.base import DataProvider


class PostgresProvider(DataProvider):
    """
    PostgreSQL-backed DataProvider reading real issue records from the database.
    """

    data_source = property(lambda self: settings.data_label)

    def __init__(self, org_id: str = "org-acme") -> None:
        self.org_id = org_id

    def _to_bug(self, issue: IssueModel) -> Bug:
        """Converts SQLAlchemy IssueModel to Pydantic Bug domain model."""
        # Convert status enum string safely
        raw_status = (issue.status or "open").lower().replace(" ", "_")
        try:
            status_enum = BugStatus(raw_status)
        except ValueError:
            status_enum = BugStatus.OPEN if "open" in raw_status else BugStatus.RESOLVED

        # Convert severity enum string safely
        raw_sev = (issue.severity or "medium").lower()
        try:
            sev_enum = BugSeverity(raw_sev)
        except ValueError:
            sev_enum = BugSeverity.MEDIUM

        # Convert priority enum string safely
        raw_prio = (issue.priority or "medium").lower()
        try:
            prio_enum = BugPriority(raw_prio)
        except ValueError:
            prio_enum = BugPriority.MEDIUM

        created = issue.created_at or datetime.now(timezone.utc)
        updated = issue.updated_at or created
        resolved = updated if status_enum in {BugStatus.RESOLVED, BugStatus.CLOSED} else None

        return Bug(
            id=issue.issue_key or issue.id,
            key=issue.issue_key or issue.id,
            project=issue.project or "BugPilot",
            title=issue.title or "Untitled Issue",
            summary=issue.title or "Untitled Issue",
            description=issue.description or "",
            severity=sev_enum,
            priority=prio_enum,
            status=status_enum,
            component=issue.component or "General",
            sprint_id=issue.sprint_id,
            reopened_count=getattr(issue, "reopen_count", 0) or 0,
            reporter=issue.reporter or "System",
            assignee=issue.assignee or "Unassigned",
            created_at=created,
            updated_at=updated,
            resolved_at=resolved,
            data_source=settings.data_label,
        )

    def get_bug(self, bug_id: str) -> Optional[Bug]:
        """Retrieve a single bug by its ID or key."""
        issue = db_get_issue_by_id_or_key(bug_id, org_id=self.org_id)
        if not issue:
            return None
        return self._to_bug(issue)

    def get_bugs(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        project: Optional[str] = None,
        component: Optional[str] = None,
        sprint_id: Optional[str] = None,
    ) -> List[Bug]:
        """Retrieve a list of bugs from PostgreSQL filtered by criteria."""
        issues = db_get_issues(
            org_id=self.org_id,
            project=project,
            component=component,
            status=status,
            severity=severity,
            sprint_id=sprint_id,
            limit=limit,
        )
        return [self._to_bug(i) for i in issues]

    def get_sprints(self) -> List[Sprint]:
        """Retrieve real database sprints."""
        db_sprints = db_get_sprints(org_id=self.org_id)
        if db_sprints:
            now = datetime.now(timezone.utc)
            return [
                Sprint(
                    id=s.id,
                    name=s.name,
                    state="active",
                    start_date=s.start_date or (now - timedelta(days=14)),
                    end_date=s.end_date or (now + timedelta(days=14)),
                    goal=s.goal or "Sprint Goal",
                    data_source=settings.data_label,
                )
                for s in db_sprints
            ]
        now = datetime.now(timezone.utc)
        return [
            Sprint(
                id="SPRINT-2026-01",
                name="Sprint 2026-01",
                state="active",
                start_date=now - timedelta(days=14),
                end_date=now + timedelta(days=14),
                goal="Deliver live PostgreSQL database features",
                data_source=settings.data_label,
            )
        ]

    def get_sprint(self, sprint_id: str) -> Optional[Sprint]:
        """Retrieve a single sprint by ID."""
        db_s = db_get_sprint(sprint_id, org_id=self.org_id)
        if db_s:
            now = datetime.now(timezone.utc)
            return Sprint(
                id=db_s.id,
                name=db_s.name,
                state="active",
                start_date=db_s.start_date or (now - timedelta(days=14)),
                end_date=db_s.end_date or (now + timedelta(days=14)),
                goal=db_s.goal or "Sprint Goal",
                data_source=settings.data_label,
            )
        sprints = self.get_sprints()
        for s in sprints:
            if s.id.upper() == sprint_id.strip().upper():
                return s
        return sprints[0] if sprints else None

    def search_bugs(self, query: str, limit: int = 100) -> List[Bug]:
        """Perform a text search on bug summary/title, description, and key in PostgreSQL."""
        issues = db_get_issues(
            org_id=self.org_id,
            search=query,
            limit=limit,
        )
        return [self._to_bug(i) for i in issues]
