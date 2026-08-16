"""
BugPilot — Database Repository & Data Mapper (Phase 18)
=======================================================
Database operations enforcing tenant isolation for Users, Organizations, Sprints, Issues, and Audit Logs.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.database.models import (
    ExecutionLogModel,
    IssueModel,
    OrganizationModel,
    SprintModel,
    UserModel,
)
from backend.database.session import Base, engine, SessionLocal
from backend.security.auth import Organization, User, UserRole, _hash_password

logger = logging.getLogger("bugpilot.database.repository")


def init_db():
    """Initializes database schema tables and seeds default multi-tenant accounts and initial issues."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed default Orgs
        if not db.query(OrganizationModel).filter_by(id="org-acme").first():
            acme = OrganizationModel(id="org-acme", name="Acme Engineering", domain="acme.com")
            globex = OrganizationModel(id="org-globex", name="Globex Corp", domain="globex.com")
            db.add_all([acme, globex])
            db.commit()

        # Seed default Users
        users_seed = [
            UserModel(
                id="usr-admin-1",
                email="admin@acme.com",
                full_name="Acme Admin",
                role=UserRole.ADMIN.value,
                org_id="org-acme",
                password_hash=_hash_password("AdminPass123!"),
            ),
            UserModel(
                id="usr-mgr-1",
                email="manager@acme.com",
                full_name="Acme Manager",
                role=UserRole.MANAGER.value,
                org_id="org-acme",
                password_hash=_hash_password("ManagerPass123!"),
            ),
            UserModel(
                id="usr-dev-2",
                email="developer@acme.com",
                full_name="Acme Developer",
                role=UserRole.DEVELOPER.value,
                org_id="org-acme",
                password_hash=_hash_password("DeveloperPass123!"),
            ),
            UserModel(
                id="usr-dev-1",
                email="engineer@acme.com",
                full_name="Acme Dev",
                role=UserRole.ENGINEER.value,
                org_id="org-acme",
                password_hash=_hash_password("EngineerPass123!"),
            ),
            UserModel(
                id="usr-view-1",
                email="viewer@acme.com",
                full_name="Acme Viewer",
                role=UserRole.VIEWER.value,
                org_id="org-acme",
                password_hash=_hash_password("ViewerPass123!"),
            ),
            UserModel(
                id="usr-globex-1",
                email="admin@globex.com",
                full_name="Globex Admin",
                role=UserRole.ADMIN.value,
                org_id="org-globex",
                password_hash=_hash_password("GlobexPass123!"),
            ),
        ]
        for u in users_seed:
            if not db.query(UserModel).filter_by(email=u.email).first():
                db.add(u)
        db.commit()

        # Safe DB migration: sanitize any legacy users with missing/invalid roles to Viewer
        valid_roles = ["Admin", "Manager", "Developer", "Engineer", "Viewer"]
        all_db_users = db.query(UserModel).all()
        for user_rec in all_db_users:
            if not user_rec.role or user_rec.role not in valid_roles:
                user_rec.role = "Viewer"
        db.commit()

        # Seed default Sprints for org-acme if none exist
        if not db.query(SprintModel).filter_by(organization_id="org-acme").first():
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            sprints_seed = [
                SprintModel(
                    id="SPRINT-2026-01",
                    name="Sprint 2026-01",
                    organization_id="org-acme",
                    start_date=now - timedelta(days=14),
                    end_date=now,
                    goal="Core Platform Stabilization",
                ),
                SprintModel(
                    id="SPRINT-2026-02",
                    name="Sprint 2026-02",
                    organization_id="org-acme",
                    start_date=now,
                    end_date=now + timedelta(days=14),
                    goal="Live Analytics Integration",
                ),
            ]
            db.add_all(sprints_seed)
            db.commit()

        # Seed initial issues for org-acme if none exist
        if not db.query(IssueModel).filter_by(organization_id="org-acme").first():
            initial_issues = [
                IssueModel(
                    id="iss-101",
                    issue_key="BP-101",
                    title="Authentication token expiry causes UI loop",
                    description="When access token expires, refresh token exchange stalls on token boundary.",
                    status="Open",
                    priority="High",
                    severity="Critical",
                    project="BugPilot",
                    component="Authentication",
                    sprint_id="SPRINT-2026-01",
                    assignee="Acme Dev",
                    reporter="Acme Admin",
                    organization_id="org-acme",
                ),
                IssueModel(
                    id="iss-102",
                    issue_key="BP-102",
                    title="Database pool connection leak under heavy query load",
                    description="Pool connections are not released cleanly when transactions timeout.",
                    status="In Progress",
                    priority="High",
                    severity="High",
                    project="BugPilot",
                    component="Database",
                    sprint_id="SPRINT-2026-01",
                    assignee="Acme Dev",
                    reporter="Acme Admin",
                    organization_id="org-acme",
                ),
                IssueModel(
                    id="iss-103",
                    issue_key="BP-103",
                    title="Slow response time in dashboard trend chart query",
                    description="Index missing on created_at column causes full table scans.",
                    status="Resolved",
                    priority="Medium",
                    severity="Medium",
                    project="BugPilot",
                    component="Analytics",
                    sprint_id="SPRINT-2026-02",
                    assignee="Acme Dev",
                    reporter="Acme Admin",
                    organization_id="org-acme",
                ),
            ]
            db.add_all(initial_issues)
            db.commit()

    except Exception as err:
        logger.error(f"Error seeding database: {err}")
        db.rollback()
    finally:
        db.close()


def db_get_user_by_email(email: str, db: Optional[Session] = None) -> Optional[UserModel]:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        return db.query(UserModel).filter(UserModel.email.ilike(email.strip())).first()
    finally:
        if close_session:
            db.close()


def db_get_user_by_id(user_id: str, db: Optional[Session] = None) -> Optional[UserModel]:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        return db.query(UserModel).filter_by(id=user_id).first()
    finally:
        if close_session:
            db.close()


def db_get_organization(org_id: str, db: Optional[Session] = None) -> Optional[OrganizationModel]:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        return db.query(OrganizationModel).filter_by(id=org_id).first()
    finally:
        if close_session:
            db.close()


def db_create_user(user_id: str, email: str, full_name: str, role: str, org_id: str, password_hash: str) -> UserModel:
    db = SessionLocal()
    try:
        new_user = UserModel(
            id=user_id,
            email=email,
            full_name=full_name,
            role=role,
            org_id=org_id,
            password_hash=password_hash,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    finally:
        db.close()

# ==========================================
# Issue CRUD Repository Functions
# ==========================================

def db_get_issues(
    org_id: str,
    project: Optional[str] = None,
    component: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    sprint_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Optional[Session] = None,
) -> List[IssueModel]:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        query = db.query(IssueModel).filter(IssueModel.organization_id == org_id)
        if project and project != "all":
            query = query.filter(IssueModel.project.ilike(project.strip()))
        if component and component != "all":
            query = query.filter(IssueModel.component.ilike(component.strip()))
        if status and status != "all":
            query = query.filter(IssueModel.status.ilike(status.strip()))
        if severity and severity != "all":
            query = query.filter(IssueModel.severity.ilike(severity.strip()))
        if sprint_id and sprint_id != "all":
            query = query.filter(IssueModel.sprint_id.ilike(sprint_id.strip()))
        if search and search.strip():
            s_val = f"%{search.strip()}%"
            query = query.filter(
                (IssueModel.title.ilike(s_val))
                | (IssueModel.issue_key.ilike(s_val))
                | (IssueModel.description.ilike(s_val))
                | (IssueModel.component.ilike(s_val))
            )
        return query.order_by(IssueModel.created_at.desc()).offset(offset).limit(limit).all()
    finally:
        if close_session:
            db.close()


def db_get_sprints(org_id: str, db: Optional[Session] = None) -> List[SprintModel]:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        return db.query(SprintModel).filter(SprintModel.organization_id == org_id).order_by(SprintModel.created_at.desc()).all()
    finally:
        if close_session:
            db.close()


def db_get_sprint(sprint_id: str, org_id: str, db: Optional[Session] = None) -> Optional[SprintModel]:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        val = sprint_id.strip()
        return (
            db.query(SprintModel)
            .filter(SprintModel.organization_id == org_id)
            .filter((SprintModel.id.ilike(val)) | (SprintModel.name.ilike(val)))
            .first()
        )
    finally:
        if close_session:
            db.close()


def db_get_issue_by_id_or_key(issue_id_or_key: str, org_id: str, db: Optional[Session] = None) -> Optional[IssueModel]:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        val = issue_id_or_key.strip()
        return (
            db.query(IssueModel)
            .filter(IssueModel.organization_id == org_id)
            .filter((IssueModel.id.ilike(val)) | (IssueModel.issue_key.ilike(val)))
            .first()
        )
    finally:
        if close_session:
            db.close()


def db_create_issue(org_id: str, data: dict, db: Optional[Session] = None) -> IssueModel:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        import uuid
        issue_id = data.get("id") or f"iss-{uuid.uuid4().hex[:8]}"
        count = db.query(IssueModel).filter(IssueModel.organization_id == org_id).count() + 101
        issue_key = data.get("issue_key") or f"BP-{count}"

        issue = IssueModel(
            id=issue_id,
            issue_key=issue_key,
            title=data.get("title", "Untitled Issue"),
            description=data.get("description", ""),
            status=data.get("status", "Open"),
            priority=data.get("priority", "Medium"),
            severity=data.get("severity", data.get("priority", "Medium")),
            project=data.get("project", "BugPilot"),
            component=data.get("component", "General"),
            sprint_id=data.get("sprint_id"),
            reopen_count=data.get("reopen_count", 0),
            assignee=data.get("assignee", "Unassigned"),
            reporter=data.get("reporter", "System"),
            organization_id=org_id,
        )
        db.add(issue)
        db.commit()
        db.refresh(issue)
        return issue
    except Exception:
        db.rollback()
        raise
    finally:
        if close_session:
            db.close()


def db_update_issue(issue_id: str, org_id: str, data: dict, db: Optional[Session] = None) -> Optional[IssueModel]:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        issue = (
            db.query(IssueModel)
            .filter(IssueModel.organization_id == org_id)
            .filter((IssueModel.id == issue_id) | (IssueModel.issue_key == issue_id))
            .first()
        )
        if not issue:
            return None

        # Detect reopen status transition (Resolved/Closed -> Open/In Progress)
        if "status" in data and data["status"] is not None:
            old_status = (issue.status or "").strip().lower()
            new_status = str(data["status"]).strip().lower()
            if old_status in ["resolved", "closed"] and new_status in ["open", "in progress", "in_progress"]:
                issue.reopen_count = (issue.reopen_count or 0) + 1

        updatable = ["title", "description", "status", "priority", "severity", "project", "component", "sprint_id", "assignee", "reporter"]
        for key in updatable:
            if key in data and data[key] is not None:
                setattr(issue, key, data[key])

        db.commit()
        db.refresh(issue)
        return issue
    except Exception:
        db.rollback()
        raise
    finally:
        if close_session:
            db.close()


def db_delete_issue(issue_id: str, org_id: str, db: Optional[Session] = None) -> bool:
    close_session = False
    if not db:
        db = SessionLocal()
        close_session = True
    try:
        issue = (
            db.query(IssueModel)
            .filter(IssueModel.organization_id == org_id)
            .filter((IssueModel.id == issue_id) | (IssueModel.issue_key == issue_id))
            .first()
        )
        if not issue:
            return False
        db.delete(issue)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        if close_session:
            db.close()

