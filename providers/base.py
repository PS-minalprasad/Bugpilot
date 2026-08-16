"""
BugPilot — DataProvider Interface
=================================
Abstract base class defining the contract for all data providers.
Ensures loose coupling between the application/agents and the physical database or API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from models.bug import Bug
from models.sprint import Sprint


class DataProvider(ABC):
    """
    Abstract interface for retrieving issue tracker datasets.
    """

    @abstractmethod
    def get_bug(self, bug_id: str) -> Optional[Bug]:
        """
        Retrieve a single bug by its ID/key.
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_sprints(self) -> List[Sprint]:
        """
        Retrieve all sprints in the system.
        """
        pass

    @abstractmethod
    def get_sprint(self, sprint_id: str) -> Optional[Sprint]:
        """
        Retrieve a single sprint by its ID.
        """
        pass

    @abstractmethod
    def search_bugs(self, query: str, limit: int = 100) -> List[Bug]:
        """
        Perform a text search on bug summary/title, description, and key.
        """
        pass
