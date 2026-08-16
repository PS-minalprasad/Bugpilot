"""
Phase 3 Test — Deterministic Analytics
========================================
Verifies all functions in AnalyticsService: summary metrics, breakdowns,
trends, aging bugs, reopen rate, risk scores, determinism, and edge cases.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from models.bug import Bug, BugSeverity, BugStatus, BugPriority
from models.sprint import Sprint, SprintStatus
from models.analytics import AnalyticsPayload
from providers.base import DataProvider
from providers.synthetic_provider import SyntheticProvider, MockJiraProvider
from analytics.service import AnalyticsService


class DummyDataProvider(DataProvider):
    """Simple provider for testing specific metric combinations."""
    def __init__(self, bugs: list[Bug], sprints: list[Sprint]) -> None:
        self.bugs = bugs
        self.sprints = sprints

    def get_bug(self, bug_id: str) -> Bug | None:
        for b in self.bugs:
            if b.id == bug_id:
                return b
        return None

    def get_bugs(self, limit=100, status=None, severity=None, project=None, component=None, sprint_id=None):
        filtered = self.bugs
        if status:
            filtered = [b for b in filtered if b.status == status]
        if severity:
            filtered = [b for b in filtered if b.severity == severity]
        if project:
            filtered = [b for b in filtered if b.project == project]
        if component:
            filtered = [b for b in filtered if b.component == component]
        if sprint_id:
            filtered = [b for b in filtered if b.sprint_id == sprint_id]
        return filtered[:limit]

    def get_sprints(self):
        return self.sprints

    def get_sprint(self, sprint_id: str):
        for s in self.sprints:
            if s.id == sprint_id:
                return s
        return None

    def search_bugs(self, query: str, limit: int = 100):
        return []


class TestAnalyticsServiceBasicMetrics:
    """Verifies basic summary and breakdown calculations."""

    @pytest.fixture
    def base_time(self) -> datetime:
        return datetime(2026, 8, 12, 12, 0, 0)

    @pytest.fixture
    def mock_data(self, base_time) -> Tuple[list[Bug], list[Sprint]]:
        # Define 5 bugs with known characteristics
        bugs = [
            Bug(
                id="BP-1",
                title="Bug 1",
                severity=BugSeverity.CRITICAL,
                priority=BugPriority.HIGH,
                status=BugStatus.OPEN,
                component="auth",
                reporter="user1",
                created_at=base_time - timedelta(days=10),
                sprint_id="SP-1",
                fix_version="v1.0.0",
                reopened_count=0
            ),
            Bug(
                id="BP-2",
                title="Bug 2",
                severity=BugSeverity.MEDIUM,
                priority=BugPriority.MEDIUM,
                status=BugStatus.IN_PROGRESS,
                component="auth",
                reporter="user2",
                created_at=base_time - timedelta(days=5),
                sprint_id="SP-1",
                fix_version="v1.0.0",
                reopened_count=1
            ),
            Bug(
                id="BP-3",
                title="Bug 3",
                severity=BugSeverity.HIGH,
                priority=BugPriority.HIGH,
                status=BugStatus.RESOLVED,
                component="database",
                reporter="user1",
                created_at=base_time - timedelta(days=8),
                resolved_at=base_time - timedelta(days=4), # MTTR = 4 days
                sprint_id="SP-1",
                fix_version="v1.1.0",
                reopened_count=0
            ),
            Bug(
                id="BP-4",
                title="Bug 4",
                severity=BugSeverity.LOW,
                priority=BugPriority.LOW,
                status=BugStatus.CLOSED,
                component="gateway",
                reporter="user3",
                created_at=base_time - timedelta(days=20),
                resolved_at=base_time - timedelta(days=10), # MTTR = 10 days
                sprint_id="SP-2",
                fix_version="v1.1.0",
                reopened_count=2
            ),
            Bug(
                id="BP-5",
                title="Bug 5",
                severity=BugSeverity.CRITICAL,
                priority=BugPriority.URGENT,
                status=BugStatus.OPEN,
                component="database",
                reporter="user2",
                created_at=base_time - timedelta(days=40), # Age = 40 days
                sprint_id="SP-2",
                fix_version="v2.0.0",
                reopened_count=0
            )
        ]

        sprints = [
            Sprint(id="SP-1", name="Sprint 1", start_date=base_time - timedelta(days=14), end_date=base_time, status=SprintStatus.ACTIVE),
            Sprint(id="SP-2", name="Sprint 2", start_date=base_time, end_date=base_time + timedelta(days=14), status=SprintStatus.FUTURE)
        ]

        return bugs, sprints

    @pytest.fixture
    def service(self, mock_data) -> AnalyticsService:
        bugs, sprints = mock_data
        provider = DummyDataProvider(bugs, sprints)
        return AnalyticsService(provider)

    def test_summary_metrics(self, service, base_time):
        payload = service.analyze(reference_time=base_time)
        sum_m = payload.summary

        assert sum_m.total_bugs == 5
        assert sum_m.open_bugs == 3        # BP-1, BP-2, BP-5
        assert sum_m.resolved_bugs == 2    # BP-3, BP-4
        assert sum_m.critical_high_bugs == 2  # BP-1 (Critical), BP-5 (Critical) are open. BP-3 is High but resolved.
        assert sum_m.reopened_bugs == 2    # BP-2, BP-4
        assert sum_m.reopen_rate == pytest.approx(0.4) # 2/5

        # Average MTTR: BP-3 is 4d, BP-4 is 10d. Avg = (4+10)/2 = 7 days.
        assert sum_m.average_resolution_time_days == pytest.approx(7.0)

    def test_breakdowns(self, service, base_time):
        payload = service.analyze(reference_time=base_time)
        bd = payload.breakdowns

        assert bd.by_component == {"auth": 2, "database": 2, "gateway": 1}
        assert bd.by_priority == {"high": 2, "medium": 1, "low": 1, "urgent": 1}
        assert bd.by_severity == {"critical": 2, "medium": 1, "high": 1, "low": 1}
        assert bd.by_status == {"open": 2, "in_progress": 1, "resolved": 1, "closed": 1}

    def test_aging_bugs(self, service, base_time):
        payload = service.analyze(reference_time=base_time)
        aging = payload.aging_bugs

        # Only open/unresolved bugs in aging (BP-1, BP-2, BP-5)
        assert len(aging) == 3
        # BP-5: created 40 days ago, so age is 40.0 days
        # BP-1: created 10 days ago, so age is 10.0 days
        # BP-2: created 5 days ago, so age is 5.0 days
        assert aging[0].bug_id == "BP-5"
        assert aging[0].age_days == pytest.approx(40.0)
        assert aging[1].bug_id == "BP-1"
        assert aging[1].age_days == pytest.approx(10.0)
        assert aging[2].bug_id == "BP-2"
        assert aging[2].age_days == pytest.approx(5.0)

    def test_sprint_trends(self, service, base_time):
        payload = service.analyze(reference_time=base_time)
        trends = payload.sprint_trends

        assert len(trends) == 2
        # SP-1 (Sprint 1): BP-1, BP-2, BP-3. Total created = 3, resolved = 1 (BP-3).
        assert trends[0].period == "Sprint 1"
        assert trends[0].created == 3
        assert trends[0].resolved == 1

        # SP-2 (Sprint 2): BP-4, BP-5. Total created = 2, resolved = 1 (BP-4).
        assert trends[1].period == "Sprint 2"
        assert trends[1].created == 2
        assert trends[1].resolved == 1


class TestRiskFormulaScores:
    """Verifies that risk scores follow the exact deterministic formulas and constraints."""

    @pytest.fixture
    def base_time(self) -> datetime:
        return datetime(2026, 8, 12, 12, 0, 0)

    def test_component_risk_score_calculation(self, base_time):
        # Case A: Component with high risk
        bugs = [
            # Open Critical bug (+15 pts)
            Bug(id="BP-1", title="A", severity=BugSeverity.CRITICAL, status=BugStatus.OPEN, component="payment", created_at=base_time - timedelta(days=20), reopened_count=0, reporter="user1"),
            # Open High bug (+15 pts)
            Bug(id="BP-2", title="B", severity=BugSeverity.HIGH, status=BugStatus.OPEN, component="payment", created_at=base_time - timedelta(days=20), reopened_count=0, reporter="user1"),
            # Reopened open bug (+10 pts, severity medium = +5 pts)
            Bug(id="BP-3", title="C", severity=BugSeverity.MEDIUM, status=BugStatus.IN_PROGRESS, component="payment", created_at=base_time - timedelta(days=20), reopened_count=1, reporter="user1"),
            # Resolved bug with slow MTTR (+10 pts)
            Bug(id="BP-4", title="D", severity=BugSeverity.LOW, status=BugStatus.RESOLVED, component="payment", created_at=base_time - timedelta(days=35), resolved_at=base_time - timedelta(days=20), reopened_count=0, reporter="user1") # MTTR = 15d
        ]
        # Calculations:
        # - Open critical/high: BP-1, BP-2. Count = 2. 2 * 15 = 30 pts (under 45 cap)
        # - Open medium/low: BP-3. Count = 1. 1 * 5 = 5 pts (under 20 cap)
        # - Reopened: BP-3. Count = 1. 1 * 10 = 10 pts (under 20 cap)
        # - Average age of open bugs (BP-1, BP-2, BP-3): all created 20 days ago. Avg age = 20d (between 14 and 30) -> +10 pts
        # - MTTR of resolved: BP-4 MTTR = 15 days (>10d) -> +10 pts
        # Expected Score: 30 + 5 + 10 + 10 + 10 = 65 points.

        provider = DummyDataProvider(bugs, [])
        service = AnalyticsService(provider)
        payload = service.analyze(reference_time=base_time)
        risks = payload.component_risks

        assert len(risks) == 1
        r = risks[0]
        assert r.name == "payment"
        assert r.risk_score == pytest.approx(65.0)
        assert len(r.reasons) > 0
        assert any("+30 pts" in reason for reason in r.reasons)
        assert r.metrics["open_bugs_count"] == 3
        assert r.metrics["open_critical_high_count"] == 2
        assert r.metrics["reopened_count"] == 1
        assert r.metrics["average_age_days"] == pytest.approx(20.0)
        assert r.metrics["mttr_days"] == pytest.approx(15.0)

    def test_risk_score_bounds_and_capping(self, base_time):
        # Exceed caps to test capping logic
        bugs = []
        # Create 5 open critical bugs -> 5 * 15 = 75 points, capped at 45
        for i in range(5):
            bugs.append(Bug(id=f"BP-{i}", title="X", severity=BugSeverity.CRITICAL, status=BugStatus.OPEN, component="heavy-buggy", created_at=base_time - timedelta(days=40), reopened_count=3, reporter="user1"))
            # Reopened count = 3 -> each bug is reopened -> 5 reopened bugs -> 50 points, capped at 20

        # Calculations:
        # - Open critical/high: 5 * 15 = 75, capped at 45.
        # - Open medium/low: 0
        # - Reopened: 5 * 10 = 50, capped at 20.
        # - Avg age: 40 days (>30) -> +15.
        # Total: 45 + 0 + 20 + 15 = 80 points.
        # MTTR: 0 (no resolved bugs).
        # Expected Score: 80.0

        provider = DummyDataProvider(bugs, [])
        service = AnalyticsService(provider)
        payload = service.analyze(reference_time=base_time)
        risks = payload.component_risks

        assert risks[0].risk_score == pytest.approx(80.0)

    def test_release_risk_score(self, base_time):
        bugs = [
            # Open Critical (+10 for open + 20 for crit/high = +30)
            Bug(id="BP-1", title="A", severity=BugSeverity.CRITICAL, status=BugStatus.OPEN, component="auth", fix_version="v1.0", created_at=base_time, reopened_count=0, reporter="user1"),
            # Open High (+10 for open + 20 for crit/high = +30)
            Bug(id="BP-2", title="B", severity=BugSeverity.HIGH, status=BugStatus.OPEN, component="auth", fix_version="v1.0", created_at=base_time, reopened_count=0, reporter="user1"),
            # Reopened resolved bug (+10 pts)
            Bug(id="BP-3", title="C", severity=BugSeverity.LOW, status=BugStatus.RESOLVED, component="auth", fix_version="v1.0", created_at=base_time - timedelta(days=2), resolved_at=base_time - timedelta(days=1), reopened_count=1, reporter="user1")
        ]
        # Calculations for v1.0 release risk:
        # - Open bugs: BP-1, BP-2. Count = 2. 2 * 10 = 20 pts (under 40 cap)
        # - Open critical/high: BP-1, BP-2. Count = 2. 2 * 20 = 40 pts (under 40 cap)
        # - Reopened bugs: BP-3. Count = 1. 1 * 10 = 10 pts (under 20 cap)
        # Expected Score: 20 + 40 + 10 = 70 points.

        provider = DummyDataProvider(bugs, [])
        service = AnalyticsService(provider)
        payload = service.analyze(reference_time=base_time)
        risks = payload.release_risks

        assert len(risks) == 1
        assert risks[0].name == "v1.0"
        assert risks[0].risk_score == pytest.approx(70.0)


class TestAnalyticsEdgeCasesAndDeterminism:
    """Verifies edge cases like empty datasets, missing fields, and deterministic outputs."""

    def test_empty_dataset(self):
        provider = DummyDataProvider([], [])
        service = AnalyticsService(provider)
        payload = service.analyze()

        # Summary should be zeroed
        assert payload.summary.total_bugs == 0
        assert payload.summary.open_bugs == 0
        assert payload.summary.reopen_rate == 0.0
        assert payload.summary.average_resolution_time_days == 0.0

        # Lists should be empty
        assert payload.creation_resolution_trends == []
        assert payload.sprint_trends == []
        assert payload.aging_bugs == []
        assert payload.component_risks == []
        assert payload.release_risks == []

    def test_deterministic_output(self):
        """MockJiraProvider is deterministic; verify AnalyticsService is also deterministic."""
        provider = MockJiraProvider(seed=42)
        service = AnalyticsService(provider)
        
        ref = datetime(2026, 8, 12, 12, 0, 0)
        res1 = service.analyze(reference_time=ref)
        res2 = service.analyze(reference_time=ref)

        # Assert summaries match exactly
        assert res1.summary.total_bugs == res2.summary.total_bugs
        assert res1.summary.open_bugs == res2.summary.open_bugs
        assert res1.summary.average_resolution_time_days == res2.summary.average_resolution_time_days
        assert res1.summary.reopen_rate == res2.summary.reopen_rate

        # Assert breakdown counts match exactly
        assert res1.breakdowns.by_component == res2.breakdowns.by_component
        assert res1.breakdowns.by_severity == res2.breakdowns.by_severity

        # Assert risks match exactly
        assert len(res1.component_risks) == len(res2.component_risks)
        for r1, r2 in zip(res1.component_risks, res2.component_risks):
            assert r1.name == r2.name
            assert r1.risk_score == r2.risk_score
            assert r1.reasons == r2.reasons
