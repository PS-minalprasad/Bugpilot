"""
BugPilot — Backward Compatibility Provider Alias
=================================================
Re-exports DataProvider, PostgresProvider, and SQLDataProvider from providers.data_provider.
Ensures zero import breakage across legacy and modern module paths.
"""

from providers.data_provider import (
    DataProvider,
    PostgresProvider,
    SQLDataProvider,
    SQLiteProvider,
)

__all__ = [
    "DataProvider",
    "PostgresProvider",
    "SQLDataProvider",
    "SQLiteProvider",
]
