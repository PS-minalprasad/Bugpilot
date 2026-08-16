"""
BugPilot — Security & Authentication Engine (Phase 15)
======================================================
Provides:
- User, Organization, and Role models (Admin, Engineer, Viewer)
- Safe password hashing & verification (HMAC-SHA256 with random salt)
- JWT Token creation, decoding, and validation
- In-Memory User & Organization store with seeded default tenants
- Tenant isolation verification
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.config import settings
from backend.core.exceptions import AuthenticationError, AuthorizationError


class UserRole(str, Enum):
    """Role-based access control roles."""
    ADMIN = "Admin"
    MANAGER = "Manager"
    DEVELOPER = "Developer"
    ENGINEER = "Engineer"
    VIEWER = "Viewer"


class Organization(BaseModel):
    """Organization / Tenant model."""
    id: str = Field(..., description="Unique Organization ID (tenant key)")
    name: str = Field(..., description="Organization display name")
    domain: str = Field(..., description="Associated domain name")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(BaseModel):
    """User account model."""
    id: str = Field(..., description="Unique User ID")
    email: str = Field(..., description="User login email")
    full_name: str = Field(..., description="User full name")
    role: UserRole = Field(..., description="Assigned RBAC role")
    org_id: str = Field(..., description="Associated organization/tenant ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


# In-Memory Security Stores
_ORGANIZATIONS_DB: Dict[str, Organization] = {}
_USERS_DB: Dict[str, User] = {}
_PASSWORD_HASHES: Dict[str, str] = {}  # user_id -> salt$hash


from passlib.context import CryptContext
import jwt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    """Secure password hashing using bcrypt via passlib."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verifies a plain text password against a stored bcrypt hash."""
    try:
        if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
            return pwd_context.verify(plain_password, stored_hash)
        # Fallback legacy hash support
        salt, _ = stored_hash.split("$", 1)
        key = settings.JWT_SECRET.encode("utf-8")
        msg = f"{salt}:{plain_password}".encode("utf-8")
        expected = f"{salt}${hmac.new(key, msg, hashlib.sha256).hexdigest()}"
        return hmac.compare_digest(expected, stored_hash)
    except Exception:
        return False


def create_access_token(user: User, expires_delta: Optional[int] = None) -> str:
    """Generates a secure PyJWT access token for a user."""
    expire_time = int(time.time()) + (expires_delta or (settings.JWT_EXPIRE_MINUTES * 60))

    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
        "org_id": user.org_id,
        "exp": expire_time,
        "iat": int(time.time()),
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates JWT token structure, signature, and expiration via PyJWT."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Authentication token has expired.")
    except jwt.PyJWTError as err:
        raise AuthenticationError(f"Invalid authentication token: {err}")
    except Exception as err:
        raise AuthenticationError(f"Could not validate authentication token: {err}")


def seed_default_tenants() -> None:
    """Seeds default organizations, roles, and users for multi-tenancy testing."""
    if _ORGANIZATIONS_DB:
        return

    # Seed Orgs
    acme_org = Organization(id="org-acme", name="Acme Engineering", domain="acme.com")
    globex_org = Organization(id="org-globex", name="Globex Corp", domain="globex.com")

    _ORGANIZATIONS_DB[acme_org.id] = acme_org
    _ORGANIZATIONS_DB[globex_org.id] = globex_org

    # Seed Users
    users_data = [
        ("usr-admin-1", "admin@acme.com", "Acme Admin", UserRole.ADMIN, "org-acme", "AdminPass123!"),
        ("usr-mgr-1", "manager@acme.com", "Acme Manager", UserRole.MANAGER, "org-acme", "ManagerPass123!"),
        ("usr-dev-2", "developer@acme.com", "Acme Developer", UserRole.DEVELOPER, "org-acme", "DeveloperPass123!"),
        ("usr-dev-1", "engineer@acme.com", "Acme Dev", UserRole.ENGINEER, "org-acme", "EngineerPass123!"),
        ("usr-view-1", "viewer@acme.com", "Acme Viewer", UserRole.VIEWER, "org-acme", "ViewerPass123!"),
        ("usr-globex-1", "admin@globex.com", "Globex Admin", UserRole.ADMIN, "org-globex", "GlobexPass123!"),
    ]

    for uid, email, name, role, org_id, pwd in users_data:
        user = User(id=uid, email=email, full_name=name, role=role, org_id=org_id)
        _USERS_DB[uid] = user
        _PASSWORD_HASHES[uid] = _hash_password(pwd)


# Seed on load
seed_default_tenants()


def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticates email and password against database repository."""
    from backend.database.repository import db_get_user_by_email
    user_model = db_get_user_by_email(email)
    if user_model and user_model.is_active and verify_password(password, user_model.password_hash):
        return User(
            id=user_model.id,
            email=user_model.email,
            full_name=user_model.full_name,
            role=UserRole(user_model.role),
            org_id=user_model.org_id,
            is_active=user_model.is_active,
        )
    for u in _USERS_DB.values():
        if u.email.lower() == email.lower() and u.is_active:
            stored_hash = _PASSWORD_HASHES.get(u.id)
            if stored_hash and verify_password(password, stored_hash):
                return u
    return None


def get_user_by_id(user_id: str) -> Optional[User]:
    from backend.database.repository import db_get_user_by_id
    user_model = db_get_user_by_id(user_id)
    if user_model:
        return User(
            id=user_model.id,
            email=user_model.email,
            full_name=user_model.full_name,
            role=UserRole(user_model.role),
            org_id=user_model.org_id,
            is_active=user_model.is_active,
        )
    return _USERS_DB.get(user_id)


def get_organization(org_id: str) -> Optional[Organization]:
    from backend.database.repository import db_get_organization
    org_model = db_get_organization(org_id)
    if org_model:
        return Organization(
            id=org_model.id,
            name=org_model.name,
            domain=org_model.domain,
        )
    return None
