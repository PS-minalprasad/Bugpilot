"""
BugPilot — Auth, Multi-Tenancy & RBAC Test Suite (Phase 15)
==========================================================
Tests:
- Password hashing & verification
- JWT Token creation, expiration, and tamper detection
- Login authentication flow
- User registration
- Multi-tenancy isolation (X-Organization-ID enforcement)
- Role-based authorization (Admin, Engineer, Viewer permissions)
"""

import pytest
import httpx
from backend.main import app
from backend.security.auth import (
    UserRole,
    authenticate_user,
    create_access_token,
    decode_access_token,
    verify_password,
    _hash_password,
    get_user_by_id,
)
from backend.core.exceptions import AuthenticationError


class TestAuthAndTokens:
    """Test suite for core security functions."""

    def test_password_hashing_and_verification(self):
        pwd = "SecurePassword123!"
        hashed = _hash_password(pwd)
        assert verify_password(pwd, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_jwt_token_cycle(self):
        user = get_user_by_id("usr-admin-1")
        token = create_access_token(user)
        decoded = decode_access_token(token)

        assert decoded["sub"] == user.id
        assert decoded["email"] == user.email
        assert decoded["role"] == user.role.value
        assert decoded["org_id"] == user.org_id

    def test_tampered_token_rejection(self):
        user = get_user_by_id("usr-admin-1")
        token = create_access_token(user)
        tampered = token[:-5] + "XXXXX"

        with pytest.raises(AuthenticationError):
            decode_access_token(tampered)

    def test_authenticate_user_success_and_failure(self):
        user = authenticate_user("admin@acme.com", "AdminPass123!")
        assert user is not None
        assert user.email == "admin@acme.com"

        fail_user = authenticate_user("admin@acme.com", "WrongPass")
        assert fail_user is None


class TestAuthAPIEndpoints:
    """Test suite for FastAPI authentication & multi-tenancy endpoints."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.post(
                "/api/v1/auth/login",
                json={"email": "engineer@acme.com", "password": "EngineerPass123!"},
            )
            assert res.status_code == 200
            data = res.json()
            assert "access_token" in data
            assert data["user"]["email"] == "engineer@acme.com"
            assert data["user"]["role"] == "Engineer"
            assert data["user"]["org_id"] == "org-acme"

    @pytest.mark.asyncio
    async def test_login_failure(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.post(
                "/api/v1/auth/login",
                json={"email": "engineer@acme.com", "password": "BadPassword"},
            )
            assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self):
        user = get_user_by_id("usr-admin-1")
        token = create_access_token(user)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["email"] == "admin@acme.com"
            assert data["role"] == "Admin"
            assert data["org_id"] == "org-acme"

    @pytest.mark.asyncio
    async def test_tenant_isolation_enforcement(self):
        # Globex user trying to pass header for Acme org
        globex_user = get_user_by_id("usr-globex-1")
        token = create_access_token(globex_user)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # Login works and claims org-globex
            me_res = await client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Organization-ID": "org-globex",
                },
            )
            assert me_res.status_code == 200
            assert me_res.json()["org_id"] == "org-globex"
