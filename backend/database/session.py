"""
BugPilot — Database Session & Engine (Phase 18)
==============================================
SQLAlchemy 2.0 database engine, session management, and health check.
"""

from __future__ import annotations

import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings

logger = logging.getLogger("bugpilot.database")

# Database Engine
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}
engine = create_engine(db_url, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative Base class for SQLAlchemy ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency delivering database session context."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_health() -> bool:
    """Verifies database connectivity via SELECT 1 query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as err:
        logger.error(f"Database health check failed: {err}")
        return False
