"""
Phase 1 Test — Pydantic Models
================================
Verifies that all Pydantic models validate correctly,
reject invalid data, and produce expected computed properties.

Acceptance criterion AC-04: Pydantic models validate.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from models.bug import Bug, BugSeverity, BugStatus, BugPriority
from models.sprint import Sprint, SprintStatus
from models.analysis import AnalysisRequest, AnalysisStatus, AnalysisScope
from models.report import AnalysisReport, ReflectionResult, ReportSection


# =============================================================================
# Bug Model
# =============================================================================

class TestBugModel:
    """Bug model validation and computed properties."""

    def _minimal_bug(self, **overrides) -> dict:
        base = {
            "id": "BP-001",
            "title": "Login page crashes on Safari",
            "severity": BugSeverity.HIGH,
            "component": "auth-service",
            "reporter": "alice",
        }
        base.update(overrides)
        return base

    def test_valid_bug_creates(self):
        bug = Bug(**self._minimal_bug())
        assert bug.id == "BP-001"

    def test_id_is_uppercased(self):
        bug = Bug(**self._minimal_bug(id="bp-001"))
        assert bug.id == "BP-001"

    def test_data_source_default(self):
        bug = Bug(**self._minimal_bug())
        assert bug.data_source == "Synthetic Demo Data"

    def test_status_default_is_open(self):
        bug = Bug(**self._minimal_bug())
        assert bug.status == BugStatus.OPEN.value

    def test_is_open_true_for_open_status(self):
        bug = Bug(**self._minimal_bug(status=BugStatus.OPEN))
        assert bug.is_open is True

    def test_is_resolved_true_for_closed(self):
        bug = Bug(**self._minimal_bug(status=BugStatus.CLOSED))
        assert bug.is_resolved is True

    def test_is_open_false_for_resolved(self):
        bug = Bug(**self._minimal_bug(status=BugStatus.RESOLVED))
        assert bug.is_open is False

    def test_blank_id_raises(self):
        with pytest.raises(ValidationError):
            Bug(**self._minimal_bug(id="   "))

    def test_blank_title_raises(self):
        with pytest.raises(ValidationError):
            Bug(**self._minimal_bug(title=""))

    def test_severity_enum_values(self):
        for sev in BugSeverity:
            bug = Bug(**self._minimal_bug(severity=sev))
            assert bug.severity is not None

    def test_all_status_values(self):
        for status in BugStatus:
            bug = Bug(**self._minimal_bug(status=status))
            assert bug.status is not None

    def test_optional_assignee_none(self):
        bug = Bug(**self._minimal_bug(assignee=None))
        assert bug.assignee is None

    def test_optional_assignee_set(self):
        bug = Bug(**self._minimal_bug(assignee="bob"))
        assert bug.assignee == "bob"

    def test_labels_default_empty(self):
        bug = Bug(**self._minimal_bug())
        assert bug.labels == []

    def test_labels_set(self):
        bug = Bug(**self._minimal_bug(labels=["regression", "ui"]))
        assert "regression" in bug.labels

    def test_age_days_is_float(self):
        bug = Bug(**self._minimal_bug())
        assert isinstance(bug.age_days, float)
        assert bug.age_days >= 0.0

    def test_model_serialises_to_dict(self):
        bug = Bug(**self._minimal_bug())
        d = bug.model_dump()
        assert "id" in d
        assert "data_source" in d
        assert d["data_source"] == "Synthetic Demo Data"


# =============================================================================
# Sprint Model
# =============================================================================

class TestSprintModel:
    """Sprint model validation."""

    def _sprint(self, **overrides) -> dict:
        now = datetime.utcnow()
        base = {
            "id": "SP-1",
            "name": "Sprint 1",
            "status": SprintStatus.ACTIVE,
            "start_date": now,
            "end_date": now + timedelta(days=14),
        }
        base.update(overrides)
        return base

    def test_valid_sprint_creates(self):
        sprint = Sprint(**self._sprint())
        assert sprint.id == "SP-1"

    def test_data_source_default(self):
        sprint = Sprint(**self._sprint())
        assert sprint.data_source == "Synthetic Demo Data"

    def test_duration_days(self):
        sprint = Sprint(**self._sprint())
        assert abs(sprint.duration_days - 14.0) < 0.01

    def test_resolution_rate_zero_bugs(self):
        sprint = Sprint(**self._sprint(total_bugs=0, resolved_bugs=0))
        assert sprint.resolution_rate == 0.0

    def test_resolution_rate_partial(self):
        sprint = Sprint(**self._sprint(total_bugs=10, resolved_bugs=4))
        assert sprint.resolution_rate == pytest.approx(0.4)

    def test_resolution_rate_full(self):
        sprint = Sprint(**self._sprint(total_bugs=10, resolved_bugs=10))
        assert sprint.resolution_rate == pytest.approx(1.0)

    def test_end_before_start_raises(self):
        now = datetime.utcnow()
        with pytest.raises(ValidationError):
            Sprint(**self._sprint(start_date=now, end_date=now - timedelta(days=1)))

    def test_resolved_exceeds_total_raises(self):
        with pytest.raises(ValidationError):
            Sprint(**self._sprint(total_bugs=5, resolved_bugs=10))


# =============================================================================
# Analysis Models
# =============================================================================

class TestAnalysisRequest:
    """AnalysisRequest validation."""

    def test_valid_request(self):
        req = AnalysisRequest(query="Show me critical bugs this sprint")
        assert req.query == "Show me critical bugs this sprint"

    def test_default_scope_is_full(self):
        req = AnalysisRequest(query="analysis query here")
        assert req.scope == AnalysisScope.FULL.value

    def test_query_too_short_raises(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(query="ab")

    def test_max_bugs_default(self):
        req = AnalysisRequest(query="valid query text")
        assert req.max_bugs == 50

    def test_max_bugs_too_high_raises(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(query="valid query text", max_bugs=501)

    def test_max_bugs_zero_raises(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(query="valid query text", max_bugs=0)

    def test_sprint_id_optional(self):
        req = AnalysisRequest(query="valid query text", sprint_id=None)
        assert req.sprint_id is None

    def test_all_scopes_valid(self):
        for scope in AnalysisScope:
            req = AnalysisRequest(query="valid query", scope=scope)
            assert req.scope is not None


# =============================================================================
# Report Models
# =============================================================================

class TestReportSection:
    """ReportSection validation."""

    def test_valid_section(self):
        s = ReportSection(title="Executive Summary", content="# Summary\n\nAll good.")
        assert s.title == "Executive Summary"
        assert s.confidence == 1.0

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValidationError):
            ReportSection(title="T", content="C", confidence=-0.1)

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValidationError):
            ReportSection(title="T", content="C", confidence=1.1)


class TestReflectionResult:
    """ReflectionResult validation."""

    def test_valid_reflection(self):
        r = ReflectionResult(
            reflection_id="ref-001",
            report_id="rpt-001",
            quality_score=0.85,
        )
        assert r.quality_score == pytest.approx(0.85, abs=0.001)

    def test_is_acceptable_high_score(self):
        r = ReflectionResult(
            reflection_id="ref-002",
            report_id="rpt-002",
            quality_score=0.75,
        )
        assert r.is_acceptable is True

    def test_is_acceptable_low_score(self):
        r = ReflectionResult(
            reflection_id="ref-003",
            report_id="rpt-003",
            quality_score=0.5,
        )
        assert r.is_acceptable is False

    def test_quality_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            ReflectionResult(reflection_id="x", report_id="y", quality_score=-0.1)

    def test_quality_score_above_one_raises(self):
        with pytest.raises(ValidationError):
            ReflectionResult(reflection_id="x", report_id="y", quality_score=1.001)

    def test_gaps_default_empty(self):
        r = ReflectionResult(reflection_id="x", report_id="y", quality_score=0.9)
        assert r.gaps == []
