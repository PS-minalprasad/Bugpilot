"""
BugPilot — Issue CRUD Routes (Phase 28)
========================================
Endpoints for creating, reading, updating, and deleting PostgreSQL issue records.
Enforces multi-tenant isolation and role-based access control (RBAC).
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.database.repository import (
    db_get_issues,
    db_get_issue_by_id_or_key,
    db_create_issue,
    db_update_issue,
    db_delete_issue,
)
from backend.security.auth import User, UserRole
from backend.security.dependencies import enforce_tenant_isolation, require_role

issues_router = APIRouter(prefix="/issues", tags=["issues"])


# Pydantic Schemas
class IssueCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512, description="Issue title/summary")
    description: Optional[str] = Field(default="", max_length=5000)
    status: str = Field(default="Open", description="Open, In Progress, Resolved, Closed")
    priority: str = Field(default="Medium", description="Low, Medium, High, Critical")
    severity: str = Field(default="Medium", description="Low, Medium, High, Critical")
    project: str = Field(default="BugPilot", description="Project key or name")
    component: str = Field(default="General", description="Component or service name")
    sprint_id: Optional[str] = Field(default=None, description="Sprint ID")
    assignee: Optional[str] = Field(default="Unassigned")
    reporter: Optional[str] = Field(default="System")


class IssueUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=512)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[str] = Field(default=None)
    priority: Optional[str] = Field(default=None)
    severity: Optional[str] = Field(default=None)
    project: Optional[str] = Field(default=None)
    component: Optional[str] = Field(default=None)
    sprint_id: Optional[str] = Field(default=None)
    assignee: Optional[str] = Field(default=None)
    reporter: Optional[str] = Field(default=None)


class IssueResponse(BaseModel):
    id: str
    issue_key: str
    title: str
    description: Optional[str]
    status: str
    priority: str
    severity: str
    project: str
    component: str
    sprint_id: Optional[str] = None
    reopen_count: int = 0
    assignee: Optional[str]
    reporter: Optional[str]
    organization_id: str
    created_at: str
    updated_at: str


def _to_issue_response(i: IssueModel) -> IssueResponse:
    return IssueResponse(
        id=i.id,
        issue_key=i.issue_key,
        title=i.title,
        description=i.description,
        status=i.status,
        priority=i.priority,
        severity=i.severity,
        project=i.project,
        component=i.component,
        sprint_id=i.sprint_id,
        reopen_count=getattr(i, "reopen_count", 0) or 0,
        assignee=i.assignee,
        reporter=i.reporter,
        organization_id=i.organization_id,
        created_at=i.created_at.isoformat() if i.created_at else "",
        updated_at=i.updated_at.isoformat() if i.updated_at else "",
    )


@issues_router.get("", response_model=List[IssueResponse], summary="GET /api/v1/issues")
async def list_issues(
    project: Optional[str] = Query(default=None),
    component: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(enforce_tenant_isolation),
):
    """Retrieves list of PostgreSQL issues for the authenticated user's organization."""
    issues = db_get_issues(
        org_id=current_user.org_id,
        project=project,
        component=component,
        status=status,
        severity=severity,
        search=search,
        limit=limit,
        offset=offset,
    )
    return [_to_issue_response(i) for i in issues]


@issues_router.get("/{issue_id}", response_model=IssueResponse, summary="GET /api/v1/issues/{issue_id}")
async def get_issue(
    issue_id: str,
    current_user: User = Depends(enforce_tenant_isolation),
):
    """Retrieves a single issue by ID or issue_key within the authenticated user's organization."""
    issue = db_get_issue_by_id_or_key(issue_id, org_id=current_user.org_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue '{issue_id}' not found.",
        )
    return _to_issue_response(issue)


@issues_router.post("", response_model=IssueResponse, status_code=status.HTTP_201_CREATED, summary="POST /api/v1/issues")
async def create_issue(
    req: IssueCreateRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.DEVELOPER, UserRole.ENGINEER])),
):
    """Creates a new issue in PostgreSQL for the active organization."""
    data = req.model_dump()
    data["reporter"] = req.reporter or current_user.email
    issue = db_create_issue(org_id=current_user.org_id, data=data)
    return _to_issue_response(issue)


@issues_router.put("/{issue_id}", response_model=IssueResponse, summary="PUT /api/v1/issues/{issue_id}")
async def update_issue(
    issue_id: str,
    req: IssueUpdateRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.DEVELOPER, UserRole.ENGINEER])),
):
    """Updates an existing issue in PostgreSQL for the active organization."""
    data = req.model_dump(exclude_unset=True)
    issue = db_update_issue(issue_id, org_id=current_user.org_id, data=data)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue '{issue_id}' not found.",
        )
    return _to_issue_response(issue)


@issues_router.delete("/{issue_id}", summary="DELETE /api/v1/issues/{issue_id}")
async def delete_issue(
    issue_id: str,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER])),
):
    """Deletes an issue from PostgreSQL for the active organization."""
    success = db_delete_issue(issue_id, org_id=current_user.org_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue '{issue_id}' not found.",
        )
    return {"status": "success", "message": f"Issue '{issue_id}' deleted successfully."}
