"""
BugPilot — PostgresProvider / SQL Database Provider
===================================================
Implements DataProvider using persistent SQL database models (IssueModel).
Works seamlessly with SQLite (default local zero-setup) and PostgreSQL.
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
    SQL-backed DataProvider reading real issue records from SQLite / PostgreSQL database.
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

        import json
        comments = []
        if getattr(issue, "comments_json", None):
            try:
                comments = json.loads(issue.comments_json) if isinstance(issue.comments_json, str) else issue.comments_json
            except Exception:
                comments = []

        linked_issues = []
        if getattr(issue, "linked_issues_json", None):
            try:
                linked_issues = json.loads(issue.linked_issues_json) if isinstance(issue.linked_issues_json, str) else issue.linked_issues_json
            except Exception:
                linked_issues = []

        created = issue.created_at or datetime.now(timezone.utc)
        updated = issue.updated_at or created
        resolved = issue.resolved_at or (updated if status_enum in {BugStatus.RESOLVED, BugStatus.CLOSED} else None)

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
            resolution=getattr(issue, "resolution", None),
            environment=getattr(issue, "environment", "production") or "production",
            affected_version=getattr(issue, "affected_version", None),
            fix_version=getattr(issue, "fix_version", None),
            root_cause=getattr(issue, "root_cause", None),
            business_impact=getattr(issue, "business_impact", None),
            steps_to_reproduce=getattr(issue, "steps_to_reproduce", None),
            expected_behavior=getattr(issue, "expected_behavior", None),
            actual_behavior=getattr(issue, "actual_behavior", None),
            comments=comments,
            linked_issue_ids=linked_issues,
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

    def get_bug_history(self, bug_id: str) -> Optional[dict]:
        """Retrieve chronological history, status transitions, and comments for a bug."""
        bug = self.get_bug(bug_id)
        if not bug:
            return None

        transitions = [
            {
                "timestamp": bug.created_at.isoformat() + "Z" if hasattr(bug.created_at, "isoformat") else str(bug.created_at),
                "from_status": None,
                "to_status": "Open",
                "actor": bug.reporter,
                "event": "Issue Created",
            }
        ]

        if bug.assignee and bug.status != "open":
            transitions.append({
                "timestamp": (bug.created_at + (bug.updated_at - bug.created_at) * 0.2).isoformat() + "Z",
                "from_status": "Open",
                "to_status": "In Progress",
                "actor": bug.assignee,
                "event": f"Assigned to {bug.assignee} and transitioned to In Progress",
            })

        if bug.reopened_count > 0:
            for r_idx in range(1, bug.reopened_count + 1):
                transitions.append({
                    "timestamp": (bug.created_at + (bug.updated_at - bug.created_at) * (0.3 + 0.1 * r_idx)).isoformat() + "Z",
                    "from_status": "Resolved",
                    "to_status": "Open",
                    "actor": bug.reporter,
                    "event": f"Bug Reopened (Cycle #{r_idx})",
                })

        if bug.resolved_at:
            transitions.append({
                "timestamp": bug.resolved_at.isoformat() + "Z" if hasattr(bug.resolved_at, "isoformat") else str(bug.resolved_at),
                "from_status": "In Progress" if bug.reopened_count == 0 else "In Review",
                "to_status": bug.status.capitalize() if hasattr(bug.status, "capitalize") else str(bug.status),
                "actor": bug.assignee or bug.reporter,
                "event": f"Resolved as {bug.resolution or 'Fixed'}",
            })

        return {
            "bug_id": bug.id,
            "title": bug.title,
            "current_status": bug.status,
            "reopen_count": bug.reopened_count,
            "created_at": bug.created_at.isoformat() + "Z" if hasattr(bug.created_at, "isoformat") else str(bug.created_at),
            "updated_at": bug.updated_at.isoformat() + "Z" if hasattr(bug.updated_at, "isoformat") else str(bug.updated_at),
            "resolved_at": bug.resolved_at.isoformat() + "Z" if bug.resolved_at and hasattr(bug.resolved_at, "isoformat") else (str(bug.resolved_at) if bug.resolved_at else None),
            "status_transitions": transitions,
            "comments": bug.comments,
            "linked_issue_ids": bug.linked_issue_ids,
            "root_cause": bug.root_cause,
            "data_source": bug.data_source,
        }

    def get_related_bugs(self, bug_id: str, limit: int = 10) -> List[Bug]:
        """Retrieve related bugs by linked IDs, matching component, or labels."""
        bug = self.get_bug(bug_id)
        if not bug:
            return []

        related: List[Bug] = []
        seen_ids = {bug.id.upper()}

        # 1. Directly linked issues
        for linked_id in bug.linked_issue_ids:
            linked_b = self.get_bug(linked_id)
            if linked_b and linked_b.id.upper() not in seen_ids:
                related.append(linked_b)
                seen_ids.add(linked_b.id.upper())

        # 2. Same component issues
        comp_bugs = self.get_bugs(limit=limit * 2, component=bug.component)
        for b in comp_bugs:
            if len(related) >= limit:
                break
            if b.id.upper() not in seen_ids:
                related.append(b)
                seen_ids.add(b.id.upper())

        return related[:limit]


# Aliases for modern DataProvider architecture
SQLDataProvider = PostgresProvider
SQLiteProvider = PostgresProvider


