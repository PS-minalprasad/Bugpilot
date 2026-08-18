"""
BugPilot — SyntheticProvider
===========================
Implements DataProvider using the deterministic in-memory synthetic data generator.
All issues carry data_source = "Synthetic Demo Data".
"""

from __future__ import annotations

from typing import List, Optional

from data.generator import generate_synthetic_data
from models.bug import Bug
from models.sprint import Sprint
from providers.base import DataProvider


class SyntheticProvider(DataProvider):
    """
    In-memory SyntheticProvider loaded with ~1000 deterministic synthetic issues.
    """

    data_source = "Synthetic Demo Data"

    def __init__(self, seed: int = 42) -> None:
        # Load synthetic data once at startup
        self._bugs, self._sprints = generate_synthetic_data(seed=seed)
        # Create lookups for faster retrieval
        self._bug_map = {b.id.upper(): b for b in self._bugs}
        self._sprint_map = {s.id.upper(): s for s in self._sprints}

    def get_bug(self, bug_id: str) -> Optional[Bug]:
        """Retrieve a single bug by its ID/key (case-insensitive)."""
        return self._bug_map.get(bug_id.strip().upper())

    def get_bugs(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        project: Optional[str] = None,
        component: Optional[str] = None,
        sprint_id: Optional[str] = None,
    ) -> List[Bug]:
        """
        Retrieve a list of bugs filtered by criteria.
        """
        filtered = self._bugs

        if status:
            s_val = status.strip().lower()
            filtered = [b for b in filtered if b.status.lower() == s_val]

        if severity:
            sev_val = severity.strip().lower()
            filtered = [b for b in filtered if b.severity.lower() == sev_val]

        if project:
            proj_val = project.strip().upper()
            filtered = [b for b in filtered if b.project.upper() == proj_val]

        if component:
            comp_val = component.strip().lower()
            filtered = [b for b in filtered if b.component.lower() == comp_val]

        if sprint_id:
            sp_val = sprint_id.strip().upper()
            filtered = [b for b in filtered if b.sprint_id and b.sprint_id.upper() == sp_val]

        return filtered[:limit]

    def search_bugs(self, query: str, limit: int = 20) -> List[Bug]:
        """Search bugs matching query string."""
        if not query or not query.strip():
            return []

        q = query.strip().lower()
        results = []
        for b in self._bugs:
            sev_str = b.severity.value if hasattr(b.severity, "value") else str(b.severity)
            stat_str = b.status.value if hasattr(b.status, "value") else str(b.status)
            if (
                q in b.id.lower()
                or q in b.summary.lower()
                or q in b.description.lower()
                or q in b.component.lower()
                or q in b.project.lower()
                or q in sev_str.lower()
                or q in stat_str.lower()
            ):
                results.append(b)

        return results[:limit]

    def get_sprints(self) -> List[Sprint]:
        """Retrieve all synthetic sprints."""
        return self._sprints

    def get_sprint(self, sprint_id: str) -> Optional[Sprint]:
        """Retrieve a single sprint by ID."""
        return self._sprint_map.get(sprint_id.strip().upper())

    def get_bug_history(self, bug_id: str) -> Optional[dict]:
        """Retrieve chronological history, status transitions, and comments for a bug."""
        bug = self.get_bug(bug_id)
        if not bug:
            return None

        # Build chronological timeline
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
        for b in self._bugs:
            if len(related) >= limit:
                break
            if b.id.upper() not in seen_ids and b.component.lower() == bug.component.lower():
                related.append(b)
                seen_ids.add(b.id.upper())

        # 3. Same project issues if still under limit
        if len(related) < limit:
            for b in self._bugs:
                if len(related) >= limit:
                    break
                if b.id.upper() not in seen_ids and b.project.upper() == bug.project.upper():
                    related.append(b)
                    seen_ids.add(b.id.upper())

        return related[:limit]


# Alias for backward compatibility during transition
MockJiraProvider = SyntheticProvider

