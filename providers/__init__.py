from __future__ import annotations
from typing import Optional

from providers.base import DataProvider
from providers.synthetic_provider import SyntheticProvider, MockJiraProvider
from providers.data_provider import PostgresProvider, SQLDataProvider, SQLiteProvider


def get_data_provider(mode: Optional[str] = None, org_id: Optional[str] = None) -> DataProvider:
    """
    Factory function returning the active DataProvider based on mode.
    Modes:
      - "sql" / "database" / "postgres" / "sqlite" (default): Database provider reading real issues from SQLite/PostgreSQL
      - "synthetic": SyntheticProvider with Synthetic Demo Data
    """
    from backend.config import settings

    active_org = org_id or "org-acme"
    provider_mode = (mode or settings.PROVIDER_MODE).lower()

    if provider_mode == "synthetic":
        return SyntheticProvider()

    return SQLDataProvider(org_id=active_org)


__all__ = [
    "DataProvider",
    "SyntheticProvider",
    "MockJiraProvider",
    "PostgresProvider",
    "SQLDataProvider",
    "SQLiteProvider",
    "get_data_provider",
]
