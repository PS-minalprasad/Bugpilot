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
            if (
                q in b.id.lower()
                or q in b.summary.lower()
                or q in b.description.lower()
                or q in b.component.lower()
                or q in b.project.lower()
            ):
                results.append(b)

        return results[:limit]

    def get_sprints(self) -> List[Sprint]:
        """Retrieve all synthetic sprints."""
        return self._sprints

    def get_sprint(self, sprint_id: str) -> Optional[Sprint]:
        """Retrieve a single sprint by ID."""
        return self._sprint_map.get(sprint_id.strip().upper())


# Alias for backward compatibility during transition
MockJiraProvider = SyntheticProvider
