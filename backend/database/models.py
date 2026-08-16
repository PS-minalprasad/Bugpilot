"""
BugPilot — SQLAlchemy ORM Models (Phase 18)
===========================================
Persistent production database schemas for:
- Organizations (Tenants)
- Users & Roles (Admin, Manager, Developer, Viewer)
- Sprints & Issues
- Execution Audit Logs
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship

from backend.database.session import Base


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    users = relationship("UserModel", back_populates="organization", cascade="all, delete-orphan")


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="Viewer")
    org_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    organization = relationship("OrganizationModel", back_populates="users")


class SprintModel(Base):
    __tablename__ = "sprints"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    goal = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    organization = relationship("OrganizationModel")


class ExecutionLogModel(Base):
    __tablename__ = "execution_logs"

    id = Column(String(64), primary_key=True, index=True)
    execution_id = Column(String(64), nullable=False, index=True)
    org_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), nullable=True)
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    elapsed_seconds = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class IssueModel(Base):
    __tablename__ = "issues"

    id = Column(String(64), primary_key=True, index=True)
    issue_key = Column(String(64), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(64), nullable=False, default="Open", index=True)
    priority = Column(String(64), nullable=False, default="Medium", index=True)
    severity = Column(String(64), nullable=False, default="Medium", index=True)
    project = Column(String(64), nullable=False, index=True)
    component = Column(String(64), nullable=False, index=True)
    sprint_id = Column(String(64), ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True, index=True)
    reopen_count = Column(Integer, default=0, nullable=False)
    assignee = Column(String(255), nullable=True)
    reporter = Column(String(255), nullable=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("OrganizationModel")
    sprint = relationship("SprintModel")

