"""
BugPilot — AnalyticsService
===========================
Executes deterministic analytics over the issue tracker datasets.
Requires a DataProvider dependency (loose coupling, no direct dataset imports).
Formula-driven risk scores are computed deterministically.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from models.bug import Bug, BugSeverity, BugStatus
from models.sprint import Sprint
from models.analytics import (
    SummaryMetrics,
    BreakdownMetrics,
    TrendPoint,
    AgingBugInfo,
    RiskMetric,
    AnalyticsPayload,
)
from providers.base import DataProvider


class AnalyticsService:
    """
    Service layer executing formula-driven, deterministic queries and metric aggregations.
    """

    def __init__(self, data_provider: DataProvider) -> None:
        self.provider = data_provider

    def analyze(
        self,
        sprint_id: Optional[str] = None,
        component: Optional[str] = None,
        project: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> AnalyticsPayload:
        """
        Run full analytics computation suite over the filtered dataset.

        Args:
            sprint_id: Optional limit to specific sprint.
            component: Optional limit to specific component.
            project: Optional limit to specific project.
            reference_time: Injection time for age calculations (defaults to datetime.utcnow()).
        """
        ref_time = reference_time or datetime.utcnow()

        # 1. Fetch data
        # Fetch a large block of bugs (up to 5000) to ensure we analyze the whole dataset.
        bugs = self.provider.get_bugs(
            limit=5000,
            sprint_id=sprint_id,
            component=component,
            project=project,
        )
        sprints = self.provider.get_sprints()

        # 2. Compute Summary Metrics
        summary = self._compute_summary(bugs, ref_time)

        # 3. Compute Breakdowns
        breakdowns = self._compute_breakdowns(bugs)

        # 4. Compute Monthly Trends
        monthly_trends = self._compute_monthly_trends(bugs)

        # 5. Compute Sprint Trends
        sprint_trends = self._compute_sprint_trends(bugs, sprints)

        # 6. Compute Aging Bugs
        aging = self._compute_aging_bugs(bugs, ref_time)

        # 7. Compute Component Risk Heatmap
        component_risks = self._compute_component_risks(bugs, ref_time)

        # 8. Compute Release Risk Heatmap
        release_risks = self._compute_release_risks(bugs)

        fallback_ds = getattr(self.provider, "data_source", "PostgreSQL")
        ds = bugs[0].data_source if bugs else fallback_ds
        return AnalyticsPayload(
            summary=summary,
            breakdowns=breakdowns,
            creation_resolution_trends=monthly_trends,
            sprint_trends=sprint_trends,
            aging_bugs=aging,
            component_risks=component_risks,
            release_risks=release_risks,
            data_source=ds,
        )

    def _compute_summary(self, bugs: List[Bug], ref_time: datetime) -> SummaryMetrics:
        total = len(bugs)
        fallback_ds = getattr(self.provider, "data_source", "PostgreSQL")
        ds = bugs[0].data_source if bugs else fallback_ds
        if total == 0:
            return SummaryMetrics(
                total_bugs=0,
                open_bugs=0,
                resolved_bugs=0,
                critical_high_bugs=0,
                reopened_bugs=0,
                reopen_rate=0.0,
                average_resolution_time_days=0.0,
                data_source=ds,
            )

        open_bugs = [b for b in bugs if b.is_open]
        resolved_bugs = [b for b in bugs if b.is_resolved]

        critical_high_open = [
            b for b in open_bugs
            if b.severity in {BugSeverity.CRITICAL.value, BugSeverity.HIGH.value}
        ]

        reopened = [b for b in bugs if b.reopened_count > 0]
        reopen_rate = len(reopened) / total

        # Average resolution time (MTTR)
        res_times = []
        for b in resolved_bugs:
            if b.resolved_at and b.created_at:
                delta = (b.resolved_at - b.created_at).total_seconds() / 86400.0
                if delta >= 0:
                    res_times.append(delta)

        avg_res_time = sum(res_times) / len(res_times) if res_times else 0.0

        return SummaryMetrics(
            total_bugs=total,
            open_bugs=len(open_bugs),
            resolved_bugs=len(resolved_bugs),
            critical_high_bugs=len(critical_high_open),
            reopened_bugs=len(reopened),
            reopen_rate=round(reopen_rate, 4),
            average_resolution_time_days=round(avg_res_time, 2),
            data_source=ds,
        )

    def _compute_breakdowns(self, bugs: List[Bug]) -> BreakdownMetrics:
        comp_counter = Counter(b.component for b in bugs)
        pri_counter = Counter(b.priority for b in bugs)
        sev_counter = Counter(b.severity for b in bugs)
        status_counter = Counter(b.status for b in bugs)

        return BreakdownMetrics(
            by_component=dict(comp_counter),
            by_priority=dict(pri_counter),
            by_severity=dict(sev_counter),
            by_status=dict(status_counter)
        )

    def _compute_monthly_trends(self, bugs: List[Bug]) -> List[TrendPoint]:
        # Group by year-month
        created_by_month = Counter()
        resolved_by_month = Counter()
        months_set = set()

        for b in bugs:
            c_month = b.created_at.strftime('%Y-%m')
            created_by_month[c_month] += 1
            months_set.add(c_month)

            if b.resolved_at:
                r_month = b.resolved_at.strftime('%Y-%m')
                resolved_by_month[r_month] += 1
                months_set.add(r_month)

        sorted_months = sorted(list(months_set))
        trends = []
        for m in sorted_months:
            trends.append(
                TrendPoint(
                    period=m,
                    created=created_by_month[m],
                    resolved=resolved_by_month[m]
                )
            )
        return trends

    def _compute_sprint_trends(self, bugs: List[Bug], sprints: List[Sprint]) -> List[TrendPoint]:
        trends = []
        # Sort sprints by start date
        sorted_sprints = sorted(sprints, key=lambda s: s.start_date)

        for s in sorted_sprints:
            s_bugs = [b for b in bugs if b.sprint_id == s.id]
            created_count = len(s_bugs)
            resolved_count = len([b for b in s_bugs if b.is_resolved])

            trends.append(
                TrendPoint(
                    period=s.name,
                    created=created_count,
                    resolved=resolved_count
                )
            )
        return trends

    def _compute_aging_bugs(self, bugs: List[Bug], ref_time: datetime) -> List[AgingBugInfo]:
        open_bugs = [b for b in bugs if b.is_open]
        aging_list = []

        for b in open_bugs:
            age = (ref_time - b.created_at).total_seconds() / 86400.0
            aging_list.append(
                AgingBugInfo(
                    bug_id=b.id,
                    summary=b.summary,
                    severity=b.severity,
                    priority=b.priority,
                    component=b.component,
                    age_days=round(max(0.0, age), 2),
                    status=b.status
                )
            )

        # Sort descending by age
        return sorted(aging_list, key=lambda x: x.age_days, reverse=True)

    def _compute_component_risks(self, bugs: List[Bug], ref_time: datetime) -> List[RiskMetric]:
        # Group bugs by component
        comp_bugs = defaultdict(list)
        for b in bugs:
            comp_bugs[b.component].append(b)

        risks = []
        for comp_name, c_bugs in comp_bugs.items():
            score = 0.0
            reasons = []

            open_bugs = [b for b in c_bugs if b.is_open]
            resolved_bugs = [b for b in c_bugs if b.is_resolved]

            # 1. Critical/High Severity open bugs (+15 points each, cap 45)
            crit_high_open = [
                b for b in open_bugs
                if b.severity in {BugSeverity.CRITICAL.value, BugSeverity.HIGH.value}
            ]
            crit_high_score = len(crit_high_open) * 15.0
            if crit_high_score > 45.0:
                crit_high_score = 45.0
            score += crit_high_score
            if crit_high_score > 0:
                reasons.append(f"Contains {len(crit_high_open)} open Critical/High bugs (+{int(crit_high_score)} pts)")

            # 2. Medium/Low Severity open bugs (+5 points each, cap 20)
            med_low_open = [
                b for b in open_bugs
                if b.severity in {BugSeverity.MEDIUM.value, BugSeverity.LOW.value}
            ]
            med_low_score = len(med_low_open) * 5.0
            if med_low_score > 20.0:
                med_low_score = 20.0
            score += med_low_score
            if med_low_score > 0:
                reasons.append(f"Contains {len(med_low_open)} open Medium/Low bugs (+{int(med_low_score)} pts)")

            # 3. Reopened bugs (+10 points each, cap 20)
            reopened = [b for b in c_bugs if b.reopened_count > 0]
            reopen_score = len(reopened) * 10.0
            if reopen_score > 20.0:
                reopen_score = 20.0
            score += reopen_score
            if reopen_score > 0:
                reasons.append(f"Contains {len(reopened)} reopened bugs (+{int(reopen_score)} pts)")

            # 4. Average age of open bugs
            if open_bugs:
                ages = [(ref_time - b.created_at).total_seconds() / 86400.0 for b in open_bugs]
                avg_age = sum(ages) / len(ages)
                if avg_age > 30:
                    score += 15.0
                    reasons.append(f"Average open bug age is {int(avg_age)} days (>30d) (+15 pts)")
                elif avg_age >= 14:
                    score += 10.0
                    reasons.append(f"Average open bug age is {int(avg_age)} days (14-30d) (+10 pts)")
                elif avg_age >= 5:
                    score += 5.0
                    reasons.append(f"Average open bug age is {int(avg_age)} days (5-14d) (+5 pts)")
            else:
                avg_age = 0.0

            # 5. MTTR of resolved bugs
            if resolved_bugs:
                res_times = [(b.resolved_at - b.created_at).total_seconds() / 86400.0 for b in resolved_bugs if b.resolved_at]
                mttr = sum(res_times) / len(res_times) if res_times else 0.0
                if mttr > 10.0:
                    score += 10.0
                    reasons.append(f"Component Mean Time to Resolve is {mttr:.1f} days (>10d) (+10 pts)")
                elif mttr >= 5.0:
                    score += 5.0
                    reasons.append(f"Component Mean Time to Resolve is {mttr:.1f} days (5-10d) (+5 pts)")
            else:
                mttr = 0.0

            # Cap and floor
            final_score = min(100.0, max(0.0, score))
            if final_score == 0:
                reasons.append("No active risk factors identified")

            risks.append(
                RiskMetric(
                    name=comp_name,
                    risk_score=round(final_score, 1),
                    reasons=reasons,
                    metrics={
                        "open_bugs_count": len(open_bugs),
                        "open_critical_high_count": len(crit_high_open),
                        "reopened_count": len(reopened),
                        "average_age_days": round(avg_age, 1),
                        "mttr_days": round(mttr, 1)
                    }
                )
            )

        # Sort descending by risk score
        return sorted(risks, key=lambda x: x.risk_score, reverse=True)

    def _compute_release_risks(self, bugs: List[Bug]) -> List[RiskMetric]:
        # Group bugs by fix_version
        rel_bugs = defaultdict(list)
        for b in bugs:
            if b.fix_version:
                rel_bugs[b.fix_version].append(b)

        risks = []
        for rel_name, r_bugs in rel_bugs.items():
            score = 0.0
            reasons = []

            open_bugs = [b for b in r_bugs if b.is_open]
            crit_high_open = [
                b for b in open_bugs
                if b.severity in {BugSeverity.CRITICAL.value, BugSeverity.HIGH.value}
            ]
            reopened = [b for b in r_bugs if b.reopened_count > 0]

            # 1. Open bugs (+10 points each, cap 40)
            open_score = len(open_bugs) * 10.0
            if open_score > 40.0:
                open_score = 40.0
            score += open_score
            if open_score > 0:
                reasons.append(f"Contains {len(open_bugs)} open bugs (+{int(open_score)} pts)")

            # 2. Open Critical/High Severity bugs (+20 points each, cap 40)
            crit_high_score = len(crit_high_open) * 20.0
            if crit_high_score > 40.0:
                crit_high_score = 40.0
            score += crit_high_score
            if crit_high_score > 0:
                reasons.append(f"Contains {len(crit_high_open)} open Critical/High bugs (+{int(crit_high_score)} pts)")

            # 3. Reopened bugs (+10 points each, cap 20)
            reopen_score = len(reopened) * 10.0
            if reopen_score > 20.0:
                reopen_score = 20.0
            score += reopen_score
            if reopen_score > 0:
                reasons.append(f"Contains {len(reopened)} reopened bugs (+{int(reopen_score)} pts)")

            # Cap and floor
            final_score = min(100.0, max(0.0, score))
            if final_score == 0:
                reasons.append("No active release risk factors identified")

            risks.append(
                RiskMetric(
                    name=rel_name,
                    risk_score=round(final_score, 1),
                    reasons=reasons,
                    metrics={
                        "open_bugs_count": len(open_bugs),
                        "open_critical_high_count": len(crit_high_open),
                        "reopened_count": len(reopened)
                    }
                )
            )

        # Sort descending by risk score
        return sorted(risks, key=lambda x: x.risk_score, reverse=True)
