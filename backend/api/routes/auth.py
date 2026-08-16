"""
BugPilot — Authentication API Router (Phase 15)
==============================================
Provides endpoints for:
- POST /api/v1/auth/login
- GET  /api/v1/auth/me
- POST /api/v1/auth/register
"""

from __future__ import annotations

import uuid
from typing import Optional, List
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status

from backend.security.auth import (
    Organization,
    User,
    UserRole,
    _PASSWORD_HASHES,
    _USERS_DB,
    _hash_password,
    authenticate_user,
    create_access_token,
    get_organization,
)
from backend.security.dependencies import enforce_tenant_isolation, get_current_user

auth_router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(..., description="User login email")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    org_id: str
    org_name: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user: UserResponse


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: UserRole = UserRole.VIEWER
    org_id: str = "org-acme"


@auth_router.post("/login", response_model=LoginResponse, summary="POST /api/v1/auth/login")
async def login(req: LoginRequest) -> LoginResponse:
    """Authenticates user and returns JWT token and organization info."""
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password credentials.",
        )

    token = create_access_token(user)
    org = get_organization(user.org_id)

    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            org_id=user.org_id,
            org_name=org.name if org else user.org_id,
        ),
    )


@auth_router.get("/me", response_model=UserResponse, summary="GET /api/v1/auth/me")
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Returns profile for the currently authenticated user."""
    org = get_organization(current_user.org_id)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        org_id=current_user.org_id,
        org_name=org.name if org else current_user.org_id,
    )


@auth_router.post("/register", response_model=UserResponse, summary="POST /api/v1/auth/register")
async def register(req: RegisterRequest) -> UserResponse:
    """Registers a new user in the organization."""
    from backend.database.repository import db_get_user_by_email, db_create_user

    existing_user = db_get_user_by_email(req.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{req.email}' already exists.",
        )

    org = get_organization(req.org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{req.org_id}' does not exist.",
        )

    # Security: Public registration defaults to VIEWER; reject self-privilege escalation to ADMIN or MANAGER
    assigned_role = req.role
    if assigned_role in [UserRole.ADMIN, UserRole.MANAGER]:
        assigned_role = UserRole.VIEWER

    new_id = f"usr-{uuid.uuid4().hex[:8]}"
    pwd_hash = _hash_password(req.password)

    db_create_user(
        user_id=new_id,
        email=req.email,
        full_name=req.full_name,
        role=assigned_role.value,
        org_id=req.org_id,
        password_hash=pwd_hash,
    )

    user = User(
        id=new_id,
        email=req.email,
        full_name=req.full_name,
        role=assigned_role,
        org_id=req.org_id,
    )

    _USERS_DB[new_id] = user
    _PASSWORD_HASHES[new_id] = pwd_hash

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        org_id=user.org_id,
        org_name=org.name,
    )


@auth_router.get("/roles", response_model=List[str], summary="GET /api/v1/auth/roles")
async def get_supported_roles() -> List[str]:
    """Returns list of supported system RBAC roles (single source of truth)."""
    return [
        UserRole.ADMIN.value.upper(),
        UserRole.MANAGER.value.upper(),
        UserRole.DEVELOPER.value.upper(),
        UserRole.VIEWER.value.upper(),
    ]




