"""
BugPilot — Security Dependencies & RBAC Enforcement (Phase 15)
=============================================================
FastAPI dependencies enforcing:
- Token-based authentication (Bearer header)
- Tenant isolation (X-Organization-ID header matching user token)
- Role-based authorization (Admin, Engineer, Viewer)
"""

from __future__ import annotations

from typing import Callable, List, Optional
from fastapi import Header, HTTPException, Request, Depends, status

from backend.core.exceptions import AuthenticationError, AuthorizationError
from backend.security.auth import (
    User,
    UserRole,
    decode_access_token,
    get_organization,
    get_user_by_id,
)


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> User:
    """FastAPI dependency extracting and verifying the authenticated user from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user identity.",
        )

    user = get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or no longer exists.",
        )

    return user


async def enforce_tenant_isolation(
    request: Request,
    current_user: User = Depends(get_current_user),
    x_organization_id: Optional[str] = Header(None),
) -> User:
    """
    Enforces multi-tenancy isolation.
    Validates that the requested organization header (if provided) matches the user's assigned organization.
    """
    target_org = x_organization_id or current_user.org_id

    if target_org != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. User '{current_user.email}' is not authorized to access organization '{target_org}'.",
        )

    # Attach tenant context to request state
    request.state.org_id = current_user.org_id
    request.state.user = current_user
    return current_user


def require_role(allowed_roles: List[UserRole]) -> Callable:
    """
    Dependency factory enforcing Role-Based Access Control (RBAC).
    """
    async def role_checker(current_user: User = Depends(enforce_tenant_isolation)) -> User:
        if current_user.role not in allowed_roles:
            role_names = [r.value for r in allowed_roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' is not authorized. Required: {', '.join(role_names)}.",
            )
        return current_user

    return role_checker
