"""
BugPilot — Database Persistence & Multi-Tenancy Test Suite (Phase 18)
====================================================================
Tests:
- SQLAlchemy ORM database initialization & schema creation
- Database repository CRUD operations
- Database health check function
- Tenant isolation at database query layer
"""

import pytest
from sqlalchemy.orm import Session

from backend.database.models import OrganizationModel, UserModel
from backend.database.repository import (
    db_get_organization,
    db_get_user_by_email,
    db_get_user_by_id,
    init_db,
)
from backend.database.session import SessionLocal, check_database_health


class TestDatabasePersistence:
    """Test suite for SQLAlchemy ORM and repository layer."""

    @pytest.fixture(autouse=True)
    def setup_database(self):
        init_db()

    def test_database_health_check(self):
        assert check_database_health() is True

    def test_seeded_organizations_exist(self):
        acme = db_get_organization("org-acme")
        globex = db_get_organization("org-globex")

        assert acme is not None
        assert acme.name == "Acme Engineering"
        assert globex is not None
        assert globex.name == "Globex Corp"

    def test_seeded_users_exist(self):
        admin = db_get_user_by_email("admin@acme.com")
        assert admin is not None
        assert admin.role == "Admin"
        assert admin.org_id == "org-acme"

        globex_admin = db_get_user_by_email("admin@globex.com")
        assert globex_admin is not None
        assert globex_admin.org_id == "org-globex"

    def test_tenant_db_query_isolation(self):
        db: Session = SessionLocal()
        try:
            acme_users = db.query(UserModel).filter_by(org_id="org-acme").all()
            globex_users = db.query(UserModel).filter_by(org_id="org-globex").all()

            acme_emails = [u.email for u in acme_users]
            globex_emails = [u.email for u in globex_users]

            assert "admin@acme.com" in acme_emails
            assert "admin@globex.com" not in acme_emails
            assert "admin@globex.com" in globex_emails
        finally:
            db.close()
