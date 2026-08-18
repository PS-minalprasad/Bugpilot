"""
BugPilot — Synthetic Data Generator
====================================
Generates deterministic, realistic Jira-compatible synthetic bugs and sprints.
All issues carry the data_source = "Synthetic Demo Data" label.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from models.bug import Bug, BugSeverity, BugStatus, BugPriority
from models.sprint import Sprint, SprintStatus


def generate_synthetic_data(seed: int = 42) -> Tuple[List[Bug], List[Sprint]]:
    """
    Generate ~1000 bugs and 20 sprints deterministically with rich evidence fields.
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
    environments = ["production", "production", "staging", "development"]

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

    root_causes = {
        "auth": [
            "Race condition in OAuth token exchange handler under concurrent requests.",
            "Missing refresh token rotation lock causing token invalidation on concurrent calls.",
            "Clock drift between auth cluster nodes exceeding JWT validation tolerance threshold.",
            "Unbounded LDAP query buffer overflowing maximum socket read size.",
        ],
        "database": [
            "Database connection pool lease timeout does not release uncommitted transaction handles.",
            "Missing composite B-tree index on (tenant_id, created_at) causing sequential table scan.",
            "Concurrent row-level locking order inverted across batch update microservices.",
            "Schema migration DDL lock held while long-running analytics query was active.",
        ],
        "gateway": [
            "Upstream reverse proxy timeout (10s) is shorter than longest downstream database transaction threshold.",
            "Header whitelist filter regex dropped non-standard X-Authorization-Token headers.",
            "TCP keepalive timeout mismatch between Cloudflare edge and internal reverse proxy.",
            "Rate limiter token bucket state failed to persist to Redis cluster during node failover.",
        ],
        "billing": [
            "Webhook idempotency key verification bypassed when retry payload contained different timestamp header.",
            "Currency formatter hardcoded USD symbol for international multi-currency tenant accounts.",
            "Stripe API client retry loop triggered parallel charge request without atomic lock.",
            "Tax API rate limit caused fallback handler to raise unhandled NullPointerException.",
        ],
        "search": [
            "Unbounded wildcard prefix aggregation caused Lucene heap memory exhaustion.",
            "Kafka search ingestion consumer group fell out of sync after node rebalance.",
            "Elasticsearch document deletion tombstone purge delayed by high indexing throughput.",
            "Fuzzy match edit distance threshold set to 2 for short 3-character keywords.",
        ],
        "logging": [
            "Synchronous disk flush enabled on high-throughput log appender thread.",
            "Circular object reference in exception context caused JSON serialization stack overflow.",
            "Log rotation cron executed before compressed archive upload completed.",
            "Env var LOG_LEVEL=DEBUG mistakenly committed in default production helm chart.",
        ],
        "scheduler": [
            "Redis distributed lock TTL expired before long-running batch job finished processing.",
            "Quartz cluster scheduler heartbeats missed due to JVM garbage collection pauses.",
            "Database connection error during cron trigger evaluation left schedule state orphaned.",
            "UTC timezone conversion omitted daylight savings offset calculation in rule engine.",
        ],
        "cache": [
            "Redis connection pool max_connections limit reached under sudden traffic spike.",
            "Missing probabilistic early expiration (XFetch) allowed cache stampede on expired home feed key.",
            "Cache key generation template lacked tenant_id namespace prefix.",
            "In-memory L1 cache failed to invalidate upon receiving Redis pub/sub eviction message.",
        ],
        "notifications": [
            "SMTP connection pool exhausted following intermittent network packet loss to mail relay.",
            "SMS gateway payload serialization omitted multi-part GSM 03.38 character length checks.",
            "APNs device token refresh hook dropped SSL context on silent push failures.",
            "Webhook exponential backoff queue overflowed memory when third-party endpoint was down.",
        ],
        "analytics": [
            "Timestamp parsing defaulted to server local timezone rather than UTC ISO-8601 offset.",
            "Aggregator loaded entire monthly event stream into single in-memory DataFrame instead of batch chunking.",
            "CSV streaming writer failed to escape embedded quotes and commas in user feedback text.",
            "Client-side beacon queue dropped events during rapid page unloads without sendBeacon fallback.",
        ],
    }

    business_impacts = {
        "auth": [
            "Degraded user login success rate by ~4.2% during peak morning authentication traffic.",
            "Customer support ticket volume increased by 28% due to recurring session logout prompts.",
            "Enterprise SSO customers unable to access workspace dashboards for approximately 35 minutes.",
        ],
        "database": [
            "API response times degraded from 120ms to 4.5s across all dependent microservices.",
            "Order creation pipeline blocked, delaying order fulfillment by up to 45 minutes.",
            "Database primary CPU utilization reached 98%, risking total application downtime.",
        ],
        "gateway": [
            "External API consumers received 502/504 Bad Gateway errors on ~6.5% of requests.",
            "Mobile app clients unable to establish real-time WebSocket feeds during 15-minute outage.",
            "Staging environment testing blocked for frontend engineering team.",
        ],
        "billing": [
            "Affected 42 customer accounts with double charge authorizations before containment.",
            "Delayed monthly subscription renewals and invoice delivery for international customers.",
            "Financial reconciliation mismatch requiring manual ledger audit by accounting team.",
        ],
        "search": [
            "E-commerce product discovery conversions declined by ~3.8% during search outage.",
            "Customer search requests returned empty or stale results for recently updated catalog items.",
            "Autocomplete suggestions failed to render on mobile web viewport.",
        ],
        "logging": [
            "Compliance audit logs temporarily missing 12 minutes of security event history.",
            "Production log shipper CPU saturation degraded collocated service response times.",
            "SRE team delayed in diagnosing secondary incident due to corrupted log format.",
        ],
        "scheduler": [
            "Automated daily reporting emails delivered twice to enterprise leadership subscribers.",
            "Database maintenance vacuuming delayed by 24 hours, increasing table bloat by 15%.",
            "Nightly batch invoice processing delayed until manual trigger by operations team.",
        ],
        "cache": [
            "Database load spiked 3.5x as requests bypassed cache directly to PostgreSQL replica.",
            "P99 latency on homepage content increased from 35ms to 850ms.",
            "Cross-user cache collision temporarily displayed wrong user preference banner.",
        ],
        "notifications": [
            "Critical security alert emails delayed by up to 25 minutes for 1,200 recipients.",
            "SMS verification codes for signup flow timed out, blocking new customer registrations.",
            "Third-party webhook consumers missed webhook event notifications during partner integration.",
        ],
        "analytics": [
            "Executive dashboard displayed daily active user counts with ~8% calculation discrepancy.",
            "Monthly executive billing export generated corrupted files requiring re-run.",
            "Product team analytics funnels temporarily under-reported mobile checkout steps.",
        ],
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

        severity = rng.choice(list(BugSeverity))
        priority = rng.choice(list(BugPriority))
        env = rng.choice(environments)

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

        # Fix version & affected version assignments
        version_idx = int((offset_days / 280.0) * len(fix_versions))
        version_idx = min(version_idx, len(fix_versions) - 1)
        fix_version = fix_versions[version_idx]
        affected_version = fix_versions[max(0, version_idx - 1)]

        # Labels
        labels = rng.sample(labels_pool, k=rng.randint(1, 3))

        assignee = rng.choice(users) if status != BugStatus.OPEN else None
        reporter = rng.choice(users)

        # Realistic Evidence Context
        root_cause_item = rng.choice(root_causes[component]) if (status in {BugStatus.RESOLVED, BugStatus.CLOSED, BugStatus.IN_PROGRESS} or rng.random() < 0.7) else None
        business_impact_item = rng.choice(business_impacts[component])
        steps_item = (
            f"1. Navigate to /{component} service endpoint.\n"
            f"2. Trigger workflow with payload matching scenario {idx}.\n"
            f"3. Observe system behavior under current workload profile."
        )
        expected_item = f"The {component} service handles the request successfully within normal SLA latency."
        actual_item = f"Encountered unexpected behavior: {summary}."

        # Realistic Engineering Comments
        comments = []
        if rng.random() < 0.85:
            comments.append({
                "author": reporter,
                "created_at": (created_at + timedelta(minutes=15)).isoformat() + "Z",
                "body": f"Logged issue during testing in {env}. Steps to reproduce verified.",
            })
        if status in {BugStatus.IN_PROGRESS, BugStatus.IN_REVIEW, BugStatus.RESOLVED, BugStatus.CLOSED} and assignee:
            comments.append({
                "author": assignee,
                "created_at": (created_at + timedelta(hours=2)).isoformat() + "Z",
                "body": f"Investigating root cause in {component} module. Identified potential fix in branch fix/{key.lower()}.",
            })
        if resolved_at and assignee:
            comments.append({
                "author": assignee,
                "created_at": (resolved_at - timedelta(minutes=10)).isoformat() + "Z",
                "body": f"Fix verified and deployed to {env}. Resolving issue.",
            })

        # Realistic Linked Issues
        linked_issue_ids = []
        if idx > 1 and rng.random() < 0.4:
            other_idx = max(1, idx - rng.randint(1, 5))
            linked_key = f"{project}-{other_idx}"
            linked_issue_ids.append(linked_key)

        description = (
            f"Issue {key}: {summary}\n\n"
            f"Environment: {env}\n"
            f"Affected Version: {affected_version}\n\n"
            f"Steps to Reproduce:\n{steps_item}\n\n"
            f"Expected Behavior:\n{expected_item}\n\n"
            f"Actual Behavior:\n{actual_item}\n\n"
            f"Severity assessment: based on {component} impact on critical workflows."
        )

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
            environment=env,
            affected_version=affected_version,
            fix_version=fix_version,
            root_cause=root_cause_item,
            business_impact=business_impact_item,
            steps_to_reproduce=steps_item,
            expected_behavior=expected_item,
            actual_behavior=actual_item,
            comments=comments,
            linked_issue_ids=linked_issue_ids,
            component=component,
            labels=labels,
            reporter=reporter,
            assignee=assignee,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            sprint_id=assigned_sprint.id,
            sprint=assigned_sprint.id,
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
