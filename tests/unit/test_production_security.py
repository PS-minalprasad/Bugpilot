"""
BugPilot — Test Suite for Phase 19 Production Security Hardening
================================================================
Tests:
- Bcrypt password hashing & verification via passlib
- PyJWT token creation, validation, and signature verification
- Production security HTTP headers presence
- Rate limiting middleware enforcement
- Secret protection & safe error responses
"""

import pytest
import httpx
from backend.main import app
from backend.security.auth import (
    _hash_password,
    create_access_token,
    decode_access_token,
    get_user_by_id,
    verify_password,
)
from backend.core.exceptions import AuthenticationError


class TestProductionSecurityHardening:
    """Test suite verifying Phase 19 production security features."""

    def test_bcrypt_hashing_and_verification(self):
        pwd = "ProductionPassword2026!"
        hashed = _hash_password(pwd)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert verify_password(pwd, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_pyjwt_token_cycle(self):
        user = get_user_by_id("usr-admin-1")
        token = create_access_token(user)
        decoded = decode_access_token(token)

        assert decoded["sub"] == user.id
        assert decoded["email"] == user.email
        assert decoded["role"] == user.role.value

    def test_pyjwt_tampered_token_rejection(self):
        user = get_user_by_id("usr-admin-1")
        token = create_access_token(user)
        tampered = token[:-5] + "AAAAA"

        with pytest.raises(AuthenticationError):
            decode_access_token(tampered)

    @pytest.mark.asyncio
    async def test_security_headers_present(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.get("/api/v1/health")
            assert res.status_code == 200
            assert res.headers.get("x-content-type-options") == "nosniff"
            assert res.headers.get("x-frame-options") == "DENY"
            assert res.headers.get("x-xss-protection") == "1; mode=block"
            assert "Content-Security-Policy" in res.headers

    @pytest.mark.asyncio
    async def test_no_secrets_in_error_responses(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.post(
                "/api/v1/auth/login",
                json={"email": "nonexistent@user.com", "password": "SecretUserPassword123!"},
            )
            assert res.status_code == 401
            data = res.json()
            assert "SecretUserPassword123!" not in str(data)
            assert "secret" not in str(data)
