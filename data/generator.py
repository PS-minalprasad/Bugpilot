"""
BugPilot — Synthetic Data Generator
====================================
Generates deterministic, realistic synthetic bugs and sprints.
All issues carry the data_source = "Synthetic Demo Data" label.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import List, Tuple

from models.bug import Bug, BugSeverity, BugStatus, BugPriority
from models.sprint import Sprint, SprintStatus


def generate_synthetic_data(seed: int = 42) -> Tuple[List[Bug], List[Sprint]]:
    """
    Generate ~1000 bugs and 20 sprints deterministically.
    """
    # 1. Setup deterministic random seed
    rng = random.Random(seed)

    # 2. Setup domain attributes
    projects = ["BP", "API", "WEB", "CORE", "INFRA", "SEC", "DATA", "UI"]
    components = [
        "auth", "database", "gateway", "billing", "search",
        "logging", "scheduler", "cache", "notifications", "analytics"
    ]
    users = ["alice", "bob", "charlie", "diana", "edward", "fiona", "george", "helen", "ian", "julia"]
    fix_versions = ["v1.0.0", "v1.1.0", "v1.2.0", "v1.3.0", "v2.0.0", "v2.1.0", "v2.2.0", "v3.0.0", "v3.1.0", "v3.2.0"]
    labels_pool = ["regression", "ui", "performance", "security", "api", "billing", "auth", "sprint-blocker", "tech-debt", "customer-facing"]

    bug_summaries = {
        "auth": [
            "OAuth login fails on Safari with timeout",
            "JWT token expiration does not trigger refresh flow",
            "MFA validation rejects valid code on first attempt",
            "Session hijack protection blocks legitimate user sessions",
            "Password reset link expired message is confusing",
            "LDAP sync job runs out of memory on large directories",
            "Rate limit on login endpoint is not applied to API keys",
            "SSO authentication leaks user emails in logs",
        ],
        "database": [
            "Connection pool leakage under heavy database load",
            "Slow query execution on active user table missing index",
            "Deadlock occurred during bulk inventory update transaction",
            "Database migrations fail due to locked schema",
            "Read replica delay causes stale product availability data",
            "Entity serialization crash on null db columns",
            "Backup restoration script fails on table constraints",
            "PostgreSQL CPU spikes to 100% on specific search queries",
        ],
        "gateway": [
            "HTTP 502 Bad Gateway during high traffic spikes",
            "API gateway strips custom auth headers from downstream requests",
            "CORS policy rejects requests from allowed staging origins",
            "SSL certificate handshake timeout on gateway proxy",
            "Websocket connection disconnects every 60 seconds",
            "Rate limiting returns 500 Internal Error instead of 429",
            "Routing rule matches incorrect API version mapping",
        ],
        "billing": [
            "Double charge occurred on customer credit card",
            "Stripe webhook fails to process subscription cancellation",
            "Invoice generation displays incorrect currency symbol",
            "Refund request times out but processes behind the scenes",
            "Billing tier upgrade does not enable premium features immediately",
            "Voucher code validation bypasses discount limits",
            "Tax calculation throws exception for non-US addresses",
        ],
        "search": [
            "Elasticsearch cluster status changes to red on node failure",
            "Search results return stale deleted product entries",
            "Autocompletion dropdown fails to load suggestions on mobile",
            "Reindexing job gets stuck in infinite retry loop",
            "Boolean search query logic acts as OR instead of AND",
            "Fuzzy search search score threshold is too low",
        ],
        "logging": [
            "Log rotation script deletes uncompressed logs",
            "Log pipeline drops logs when buffer size is exceeded",
            "JSON log formatting is broken for nested exception stacks",
            "Debug logs accidentally printed in production profile",
            "Log shipper CPU spikes on reading large log files",
        ],
        "scheduler": [
            "Cron job triggers twice in concurrent cluster nodes",
            "Delayed task execution queue gets stuck on blocked workers",
            "Cleanup task fails to release resource locks on completion",
            "Scheduled job fails to start after database restart",
            "Task rescheduling calculation uses wrong timezone offset",
        ],
        "cache": [
            "Redis connection pool exhausted under concurrent cache updates",
            "Cache stampede on homepage content expiration",
            "Invalid cache eviction policy causes out of memory",
            "Cache key collision between users on profile queries",
            "Local memory cache does not sync across clustered app servers",
        ],
        "notifications": [
            "Email notification queue fails to send due to SMTP credentials",
            "SMS notification payload exceeds character limits",
            "Push notification token update fails on iOS device token refresh",
            "Webhooks drop retry events on slow client server response",
            "Unsubscribe link fails to update user preferences database",
        ],
        "analytics": [
            "Daily report metric calculation drops timezone adjustments",
            "Analytics pipeline throws OutOfMemoryError on aggregations",
            "User session duration tracking counts sleep mode time",
            "Export data utility generates corrupted CSV format",
            "Click stream tracking misses events under heavy UI load",
        ]
    }

    # 3. Generate 20 sprints
    # Each sprint lasts 14 days. Sprints cover the last 280 days.
    sprints: List[Sprint] = []
    base_time = datetime(2026, 8, 12, 12, 0, 0)
    start_date = base_time - timedelta(days=280)

    for i in range(1, 21):
        s_start = start_date + timedelta(days=(i - 1) * 14)
        s_end = s_start + timedelta(days=14)

        if s_end <= base_time - timedelta(days=14):
            status = SprintStatus.CLOSED
        elif s_start <= base_time:
            status = SprintStatus.ACTIVE
        else:
            status = SprintStatus.FUTURE

        sprint = Sprint(
            id=f"SP-{i}",
            name=f"Sprint {i}",
            goal=f"Stabilize system and complete features for Sprint {i} cycle",
            status=status,
            start_date=s_start,
            end_date=s_end,
            data_source="Synthetic Demo Data"
        )
        sprints.append(sprint)

    # 4. Generate ~1000 bugs
    bugs: List[Bug] = []
    total_bugs_count = 1000

    # Ensure deterministic but structured distribution over time.
    # Bugs are created across the 280 days duration.
    for idx in range(1, total_bugs_count + 1):
        # Choose project
        project = rng.choice(projects)
        key = f"{project}-{idx}"

        # Choose component
        component = rng.choice(components)

        # Retrieve a matching summary or construct a generic one
        summary_list = bug_summaries[component]
        summary = rng.choice(summary_list)
        if rng.random() > 0.6:
            summary = f"[{component.upper()}] {summary} (Case {idx})"
        
        description = (
            f"Detailed description of the issue {key}.\n"
            f"Steps to reproduce:\n1. Open application\n2. Trigger component {component}\n"
            f"3. Issue occurred: {summary}.\n\n"
            f"Severity assessment: based on component impact on critical workflows.\n"
            f"This bug is generated as part of the Synthetic Demo Data."
        )

        severity = rng.choice(list(BugSeverity))
        priority = rng.choice(list(BugPriority))

        # Assign creation date somewhere in the 280 days window
        offset_days = rng.uniform(0, 275)
        created_at = start_date + timedelta(days=offset_days)

        # Link to appropriate sprint
        assigned_sprint = None
        for s in sprints:
            if s.start_date <= created_at < s.end_date:
                assigned_sprint = s
                break
        
        if assigned_sprint is None:
            assigned_sprint = sprints[-1]

        # Determine bug status, resolution, and resolution date
        is_historical = assigned_sprint.status == SprintStatus.CLOSED

        reopened_count = 0
        if rng.random() < 0.15:  # 15% reopen rate
            reopened_count = rng.randint(1, 3)

        if is_historical:
            if rng.random() < 0.92:
                status = rng.choice([BugStatus.RESOLVED, BugStatus.CLOSED])
                resolution = rng.choice(["Done", "Fixed", "Done"])
                resolve_days = rng.uniform(0.1, 7.0)
                resolved_at = created_at + timedelta(days=resolve_days)
            else:
                if rng.random() < 0.5:
                    status = rng.choice([BugStatus.WONT_FIX, BugStatus.DUPLICATE])
                    resolution = "Won't Fix" if status == BugStatus.WONT_FIX else "Duplicate"
                    resolved_at = created_at + timedelta(days=1)
                else:
                    status = BugStatus.OPEN
                    resolution = None
                    resolved_at = None
        else:
            if rng.random() < 0.4:
                status = rng.choice([BugStatus.OPEN, BugStatus.IN_PROGRESS, BugStatus.IN_REVIEW])
                resolution = None
                resolved_at = None
            else:
                status = BugStatus.RESOLVED
                resolution = "Done"
                resolve_days = rng.uniform(0.1, 3.0)
                resolved_at = created_at + timedelta(days=resolve_days)

        # Make sure updated_at is sensible
        if resolved_at:
            updated_at = resolved_at + timedelta(minutes=rng.uniform(5, 120))
        else:
            if reopened_count > 0:
                updated_at = created_at + timedelta(days=rng.uniform(1.0, 5.0))
            else:
                updated_at = created_at

        # Fix version assignments
        version_idx = int((offset_days / 280.0) * len(fix_versions))
        version_idx = min(version_idx, len(fix_versions) - 1)
        fix_version = fix_versions[version_idx]

        # Labels
        labels = rng.sample(labels_pool, k=rng.randint(1, 3))

        assignee = rng.choice(users) if status != BugStatus.OPEN else None
        reporter = rng.choice(users)

        bug = Bug(
            id=key,
            key=key,
            project=project,
            issue_type="Bug",
            title=summary,
            summary=summary,
            description=description,
            severity=severity,
            priority=priority,
            status=status,
            resolution=resolution,
            component=component,
            labels=labels,
            reporter=reporter,
            assignee=assignee,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            sprint_id=assigned_sprint.id,
            sprint=assigned_sprint.id,
            fix_version=fix_version,
            reopened_count=reopened_count,
            data_source="Synthetic Demo Data"
        )
        bugs.append(bug)

    # 5. Populate Sprint Metrics dynamically
    for s in sprints:
        s_bugs = [b for b in bugs if b.sprint_id == s.id]
        s.total_bugs = len(s_bugs)
        s.resolved_bugs = len([b for b in s_bugs if b.is_resolved])
        s.critical_bugs = len([b for b in s_bugs if b.severity in {BugSeverity.CRITICAL, BugSeverity.HIGH}])

    return bugs, sprints
