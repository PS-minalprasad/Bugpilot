from __future__ import annotations
from typing import Optional

from providers.base import DataProvider
from providers.synthetic_provider import SyntheticProvider, MockJiraProvider
from providers.postgres_provider import PostgresProvider


def get_data_provider(mode: Optional[str] = None, org_id: Optional[str] = None) -> DataProvider:
    """
    Factory function returning the active DataProvider based on mode.
    Modes:
      - "postgres" (default): PostgresProvider reading real issues from PostgreSQL
      - "synthetic": SyntheticProvider with Synthetic Demo Data
    """
    from backend.config import settings

    active_org = org_id or "org-acme"
    provider_mode = (mode or settings.PROVIDER_MODE).lower()

    if provider_mode == "synthetic":
        return SyntheticProvider()

    return PostgresProvider(org_id=active_org)


__all__ = ["DataProvider", "SyntheticProvider", "MockJiraProvider", "PostgresProvider", "get_data_provider"]
