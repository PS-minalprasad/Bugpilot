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
        # Safe automatic migration for SQLite tables with new columns
        try:
            from sqlalchemy import text
            columns_info = db.execute(text("PRAGMA table_info(issues)")).fetchall()
            existing_cols = {col[1] for col in columns_info}
            if existing_cols:
                new_cols = {
                    "resolution": "TEXT",
                    "environment": "TEXT DEFAULT 'production'",
                    "affected_version": "TEXT",
                    "fix_version": "TEXT",
                    "root_cause": "TEXT",
                    "business_impact": "TEXT",
                    "steps_to_reproduce": "TEXT",
                    "expected_behavior": "TEXT",
                    "actual_behavior": "TEXT",
                    "comments_json": "TEXT",
                    "linked_issues_json": "TEXT",
                    "resolved_at": "DATETIME",
                }
                for col_name, col_type in new_cols.items():
                    if col_name not in existing_cols:
                        db.execute(text(f"ALTER TABLE issues ADD COLUMN {col_name} {col_type}"))
                db.commit()
        except Exception as mig_err:
            logger.warning(f"Auto-migration check skipped or failed: {mig_err}")
            db.rollback()

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

        # Backfill and enrich all issues with realistic Jira evidence
        existing_issues = db.query(IssueModel).filter_by(organization_id="org-acme").all()
        
        # Comprehensive catalog of realistic engineering bugs with evidence
        realistic_catalog = [
            {
                "issue_key": "BP-101",
                "title": "Authentication token expiry causes UI loop",
                "component": "Authentication",
                "status": "Open",
                "priority": "High",
                "severity": "Critical",
                "environment": "production",
                "affected_version": "v2.1.0",
                "fix_version": "v2.2.0",
                "description": "When access token expires, refresh token exchange stalls on token boundary in Safari and Chrome.",
                "root_cause": "Race condition in OAuth token exchange handler under concurrent requests causes token invalidation.",
                "business_impact": "Degraded user login success rate by ~4.2% during peak morning authentication traffic.",
                "steps_to_reproduce": "1. Authenticate with valid SSO credentials.\n2. Open second concurrent session in new browser tab.\n3. Attempt to trigger token refresh.\n4. Observe token invalidation error.",
                "expected_behavior": "System seamlessly refreshes access token and maintains active session.",
                "actual_behavior": "Session expires abruptly with HTTP 401 and redirects user to login screen.",
                "comments": [
                    {"author": "Acme Admin", "created_at": "2026-08-01T10:15:00Z", "body": "Reported by customer support after 15 user tickets."},
                    {"author": "Acme Dev", "created_at": "2026-08-01T12:30:00Z", "body": "Reproduced on Safari 17.2 and Chrome 124."}
                ],
                "linked_issues": ["BP-102", "BP-133"],
            },
            {
                "issue_key": "BP-102",
                "title": "Database pool connection leak under heavy query load",
                "component": "Database",
                "status": "In Progress",
                "priority": "High",
                "severity": "High",
                "environment": "production",
                "affected_version": "v2.0.0",
                "fix_version": "v2.2.0",
                "description": "Pool connections are not released cleanly when transactions timeout under heavy dashboard load.",
                "root_cause": "Database connection pool lease timeout does not release uncommitted transaction handles.",
                "business_impact": "API response times degraded from 120ms to 4.5s across all dependent microservices.",
                "steps_to_reproduce": "1. Run load test with 200 concurrent requests to /analytics/trends.\n2. Observe active connection pool count climbing to max_connections (50).\n3. Pool fails to recycle idle handles.",
                "expected_behavior": "Transactions timeout and connection handles return to pool immediately.",
                "actual_behavior": "Active connections stay pinned, starving incoming requests with 500 ConnectionTimeout.",
                "comments": [
                    {"author": "Acme Dev", "created_at": "2026-08-03T14:00:00Z", "body": "Identified SQLAlchemy pool recycling misconfiguration."}
                ],
                "linked_issues": ["BP-101", "BP-103"],
            },
            {
                "issue_key": "BP-103",
                "title": "Slow response time in dashboard trend chart query",
                "component": "Analytics",
                "status": "Resolved",
                "priority": "Medium",
                "severity": "Medium",
                "environment": "production",
                "affected_version": "v1.3.0",
                "fix_version": "v2.0.0",
                "resolution": "Fixed",
                "description": "Index missing on created_at column causes full table scans on large issue datasets.",
                "root_cause": "Missing composite B-tree index on (organization_id, created_at) causing sequential table scan.",
                "business_impact": "Executive dashboard trend chart load times increased from 200ms to 3.8s.",
                "steps_to_reproduce": "1. Open dashboard page with 10k issues.\n2. Filter by 90-day time window.\n3. Measure query execution time.",
                "expected_behavior": "Query returns within 250ms using indexed range scan.",
                "actual_behavior": "Full table scan triggers database CPU spike and 3.8s query duration.",
                "comments": [
                    {"author": "Acme Dev", "created_at": "2026-08-05T09:00:00Z", "body": "Added migration for index ix_issues_org_created. Query time dropped to 45ms."}
                ],
                "linked_issues": ["BP-102"],
            },
            {
                "issue_key": "BP-124",
                "title": "Payment API returns 500 error during checkout",
                "component": "Payments",
                "status": "Open",
                "priority": "High",
                "severity": "Critical",
                "environment": "production",
                "affected_version": "v2.2.0",
                "fix_version": "v2.3.0",
                "description": "Checkout requests intermittently return HTTP 500 when a customer applies a discount code.",
                "root_cause": "Stripe webhook payload signature validation fails when customer applies discount coupon due to unescaped UTF-8 currency symbols.",
                "business_impact": "Checkout abandonment increased by 14.5%, blocking approximately $28,000 in daily transactions across EU and US checkout flows.",
                "steps_to_reproduce": "1. Add product to cart.\n2. Proceed to checkout.\n3. Apply coupon code 'SUMMER2026'.\n4. Click 'Pay Now'.\n5. Observe HTTP 500 InternalServerError from /api/payments/checkout.",
                "expected_behavior": "Payment gateway applies discount calculation and processes transaction successfully with HTTP 200.",
                "actual_behavior": "Payment gateway throws unhandled JSONDecodeError and returns HTTP 500, stranding customer transaction in pending state.",
                "comments": [
                    {"author": "Billing Lead", "created_at": "2026-08-10T11:00:00Z", "body": "Confirmed regression introduced in payment gateway SDK bump v3.4.1."},
                    {"author": "Payments SRE", "created_at": "2026-08-10T13:20:00Z", "body": "Hotfix branch prepared with sanitized string encoding."}
                ],
                "linked_issues": ["BP-101", "BP-102"],
            },
            {
                "issue_key": "BP-132",
                "title": "Login page crash on biometric Passkey authentication",
                "component": "Authentication",
                "status": "Open",
                "priority": "High",
                "severity": "Critical",
                "environment": "production",
                "affected_version": "v2.2.0",
                "fix_version": "v2.3.0",
                "description": "WebAuthn assertion verification throws unhandled TypeError when client public key credential contains empty authenticatorData.",
                "root_cause": "WebAuthn client credential parser assumes non-null authenticatorData buffer without checking byte length.",
                "business_impact": "Prevents 100% of Passkey / FaceID users on iOS 17 and macOS Sonoma from logging in.",
                "steps_to_reproduce": "1. Navigate to /login.\n2. Click 'Sign in with Passkey'.\n3. Complete biometric prompt.\n4. Observe frontend React crash.",
                "expected_behavior": "Biometric assertion completes and session cookie is set.",
                "actual_behavior": "Frontend crashes with Uncaught TypeError: Cannot read property 'byteLength' of undefined.",
                "comments": [
                    {"author": "Frontend Lead", "created_at": "2026-08-11T16:00:00Z", "body": "Affects all Safari and Chrome biometric logins."}
                ],
                "linked_issues": ["BP-101", "BP-133"],
            },
            {
                "issue_key": "BP-133",
                "title": "Authentication session fixation on customer portal login",
                "component": "Authentication",
                "status": "Open",
                "priority": "High",
                "severity": "Critical",
                "environment": "production",
                "affected_version": "v2.1.0",
                "fix_version": "v2.3.0",
                "description": "Customer portal session ID remains unchanged across privilege boundaries after enterprise SSO login.",
                "root_cause": "JWT refresh token rotation does not invalidate existing session cookie on password change or privilege upgrade.",
                "business_impact": "Security compliance vulnerability in SOC2 audit; potential session hijacking risk for customer enterprise accounts.",
                "steps_to_reproduce": "1. Log in on browser A.\n2. Change password on browser B.\n3. Verify session cookie on browser A.\n4. Observe session remains active indefinitely.",
                "expected_behavior": "Password change invalidates all active JWT refresh tokens and forces re-authentication across all devices.",
                "actual_behavior": "Old session cookie remains active until 24-hour expiration.",
                "comments": [
                    {"author": "Security SecOps", "created_at": "2026-08-12T09:00:00Z", "body": "Reported via bug bounty program. Severity set to Critical."}
                ],
                "linked_issues": ["BP-101", "BP-132"],
            },
            {
                "issue_key": "BP-999",
                "title": "Authentication token validation error on distributed edge cache",
                "component": "Authentication",
                "status": "Open",
                "priority": "High",
                "severity": "Critical",
                "environment": "production",
                "affected_version": "v2.2.0",
                "fix_version": "v2.3.0",
                "description": "Edge CDN nodes reject valid access tokens due to clock skew between regional edge gateways.",
                "root_cause": "JWT 'nbf' (not before) assertion tolerance set to 0 seconds instead of standard 60-second leeway.",
                "business_impact": "Intermittent 401 Unauthorized errors for ~2.3% of global users on edge proxy endpoints.",
                "steps_to_reproduce": "1. Issue access token in US-East.\n2. Immediately query edge gateway in EU-Central.\n3. Observe 401 TokenNotYetValid error.",
                "expected_behavior": "Gateway allows 60s clock skew window for distributed validation.",
                "actual_behavior": "Token rejected with HTTP 401.",
                "comments": [
                    {"author": "Infrastructure SRE", "created_at": "2026-08-13T10:00:00Z", "body": "Leeway parameter added to JWT validation config."}
                ],
                "linked_issues": ["BP-101"],
            }
        ]

        # Catalog lookup by issue_key
        catalog_map = {item["issue_key"]: item for item in realistic_catalog}

        # Components pool for generating realistic metadata on synthetic developer test issues
        comp_pool = [
            ("Payments", "Stripe webhook payment capture timeout on credit card settlement", "Stripe payment gateway", "Critical", "High"),
            ("Billing", "Invoice PDF rendering fails on multi-currency tax calculation", "Invoice billing engine", "High", "High"),
            ("Checkout", "Cart checkout pricing discrepancy when coupon applied", "Checkout cart service", "High", "Medium"),
            ("Notifications", "Email notification queue worker memory leak under batch dispatch", "Notification queue", "Medium", "Medium"),
            ("Database", "Database read replica replication lag exceeds 45 seconds", "Database cluster", "High", "High"),
            ("API", "GraphQL rate limiter returns 429 prematurely on batched queries", "API gateway", "Medium", "Medium"),
            ("Search", "Elasticsearch index sync lagging behind database write stream", "Search index service", "Medium", "Low"),
            ("Frontend", "React memory leak in real-time WebSocket dashboard subscription", "Frontend UI", "Medium", "Medium"),
            ("Analytics", "Aggregation pipeline drop events on high-throughput Kafka topic", "Analytics worker", "High", "Medium"),
            ("Security", "CORS policy misconfiguration blocks mobile WebView API calls", "Security middleware", "High", "High"),
        ]

        import json
        if not existing_issues:
            # Seed full catalog
            for idx, c_item in enumerate(realistic_catalog):
                new_iss = IssueModel(
                    id=f"iss-{idx+101}",
                    issue_key=c_item["issue_key"],
                    title=c_item["title"],
                    description=c_item["description"],
                    status=c_item["status"],
                    priority=c_item["priority"],
                    severity=c_item["severity"],
                    environment=c_item["environment"],
                    affected_version=c_item["affected_version"],
                    fix_version=c_item["fix_version"],
                    resolution=c_item.get("resolution"),
                    root_cause=c_item["root_cause"],
                    business_impact=c_item["business_impact"],
                    steps_to_reproduce=c_item["steps_to_reproduce"],
                    expected_behavior=c_item["expected_behavior"],
                    actual_behavior=c_item["actual_behavior"],
                    comments_json=json.dumps(c_item["comments"]),
                    linked_issues_json=json.dumps(c_item["linked_issues"]),
                    project="BugPilot",
                    component=c_item["component"],
                    sprint_id="SPRINT-2026-01",
                    assignee="Acme Dev",
                    reporter="Acme Admin",
                    organization_id="org-acme",
                )
                db.add(new_iss)
            db.commit()
        else:
            # Backfill existing issues
            for idx, iss in enumerate(existing_issues):
                c_data = catalog_map.get(iss.issue_key)
                if c_data:
                    iss.title = c_data["title"]
                    iss.component = c_data["component"]
                    iss.status = c_data["status"]
                    iss.priority = c_data["priority"]
                    iss.severity = c_data["severity"]
                    iss.environment = c_data["environment"]
                    iss.affected_version = c_data["affected_version"]
                    iss.fix_version = c_data["fix_version"]
                    iss.description = c_data["description"]
                    iss.root_cause = c_data["root_cause"]
                    iss.business_impact = c_data["business_impact"]
                    iss.steps_to_reproduce = c_data["steps_to_reproduce"]
                    iss.expected_behavior = c_data["expected_behavior"]
                    iss.actual_behavior = c_data["actual_behavior"]
                    iss.comments_json = json.dumps(c_data["comments"])
                    iss.linked_issues_json = json.dumps(c_data["linked_issues"])
                elif "Developer Test Issue" in (iss.title or "") or not iss.root_cause:
                    comp_name, comp_title, comp_service, comp_sev, comp_pri = comp_pool[idx % len(comp_pool)]
                    iss.title = f"{comp_title} (Issue #{idx+1})"
                    iss.component = comp_name
                    iss.severity = comp_sev if iss.severity in {"Critical", "High"} else "Medium"
                    iss.priority = comp_pri
                    iss.environment = "production"
                    iss.affected_version = "v2.1.0"
                    iss.fix_version = "v2.2.0"
                    iss.description = f"Automated telemetry detected performance degradation and exception spikes in {comp_service}."
                    iss.root_cause = f"Unhandled boundary condition in {comp_service} under concurrent workload."
                    iss.business_impact = f"Elevated latency and error rate in {comp_name} services affecting ~1.8% of daily transactions."
                    iss.steps_to_reproduce = f"1. Send concurrent API payload to /{comp_name.lower()}/process.\n2. Monitor server logs.\n3. Observe timeout exception."
                    iss.expected_behavior = f"{comp_service} handles concurrent request payload within 200ms SLA."
                    iss.actual_behavior = f"{comp_service} stalls with connection timeout after 5000ms."
                    iss.comments_json = json.dumps([{"author": "Engineering Lead", "created_at": "2026-08-08T10:00:00Z", "body": "Triage verified root cause in service worker."}])
                    iss.linked_issues_json = json.dumps(["BP-101", "BP-102"])
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
                | (IssueModel.severity.ilike(s_val))
                | (IssueModel.status.ilike(s_val))
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
        import json
        import uuid
        issue_id = data.get("id") or f"iss-{uuid.uuid4().hex[:8]}"
        
        # Ensure unique issue_key per organization
        provided_key = data.get("issue_key")
        if provided_key:
            existing = db.query(IssueModel).filter(IssueModel.organization_id == org_id, IssueModel.issue_key == provided_key).first()
            if existing:
                count = db.query(IssueModel).filter(IssueModel.organization_id == org_id).count() + 101
                issue_key = f"BP-{count}-{uuid.uuid4().hex[:4]}"
            else:
                issue_key = provided_key
        else:
            count = db.query(IssueModel).filter(IssueModel.organization_id == org_id).count() + 101
            issue_key = f"BP-{count}"

        # JSON encode comments and linked issues if provided as list
        comments = data.get("comments") or data.get("comments_json") or []
        if isinstance(comments, list):
            comments_json = json.dumps(comments)
        else:
            comments_json = str(comments)

        linked_issues = data.get("linked_issue_ids") or data.get("linked_issues_json") or []
        if isinstance(linked_issues, list):
            linked_issues_json = json.dumps(linked_issues)
        else:
            linked_issues_json = str(linked_issues)

        issue = IssueModel(
            id=issue_id,
            issue_key=issue_key,
            title=data.get("title", "Untitled Issue"),
            description=data.get("description", ""),
            status=data.get("status", "Open"),
            priority=data.get("priority", "Medium"),
            severity=data.get("severity", data.get("priority", "Medium")),
            resolution=data.get("resolution"),
            environment=data.get("environment", "production"),
            affected_version=data.get("affected_version"),
            fix_version=data.get("fix_version"),
            root_cause=data.get("root_cause"),
            business_impact=data.get("business_impact"),
            steps_to_reproduce=data.get("steps_to_reproduce"),
            expected_behavior=data.get("expected_behavior"),
            actual_behavior=data.get("actual_behavior"),
            comments_json=comments_json,
            linked_issues_json=linked_issues_json,
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
        import json
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

        updatable = [
            "title", "description", "status", "priority", "severity", "resolution",
            "environment", "affected_version", "fix_version", "root_cause",
            "business_impact", "steps_to_reproduce", "expected_behavior",
            "actual_behavior", "project", "component", "sprint_id",
            "assignee", "reporter", "resolved_at"
        ]
        for key in updatable:
            if key in data and data[key] is not None:
                setattr(issue, key, data[key])

        if "comments" in data and data["comments"] is not None:
            issue.comments_json = json.dumps(data["comments"]) if isinstance(data["comments"], list) else str(data["comments"])
        elif "comments_json" in data and data["comments_json"] is not None:
            issue.comments_json = str(data["comments_json"])

        if "linked_issue_ids" in data and data["linked_issue_ids"] is not None:
            issue.linked_issues_json = json.dumps(data["linked_issue_ids"]) if isinstance(data["linked_issue_ids"], list) else str(data["linked_issue_ids"])
        elif "linked_issues_json" in data and data["linked_issues_json"] is not None:
            issue.linked_issues_json = str(data["linked_issues_json"])

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

