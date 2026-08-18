"""
BugPilot — Unit & Integration Test Suite for Report & Reflection Agents (Phase 8)
====================================================================================
Verifies:
  - ReportAgent generating structured AnalysisReport from MCP ground-truth evidence without inventing metrics.
  - ReflectionAgent evaluating correct answers -> CONFIRM.
  - ReflectionAgent evaluating incorrect/unsupported answers -> CORRECT with exact corrections.
  - Detection of unsupported claims (e.g. wrong top risk component).
  - Validation of inputs and error safety.
"""

import pytest
from agents.reporting import ReflectionAgent, ReportAgent
from backend.core.exceptions import ValidationError
from mcp_client import MCPClient
from models.report import AnalysisReport, ReflectionResult


class TestReportAndReflectionAgents:
    """Test suite for Phase 8 Report and Reflection Agents."""

    @pytest.mark.asyncio
    async def test_report_agent_generation(self):
        """Verify ReportAgent synthesizes clean AnalysisReport from MCP ground truth evidence."""
        async with MCPClient() as client:
            b_metrics = await client.call_tool("get_bug_metrics")
            r_risk = await client.call_tool("get_component_risk")
            t_trends = await client.call_tool("get_bug_trends")

            report_agent = ReportAgent()
            report = report_agent.generate_report(
                query="Synthesize full bug intelligence report",
                bug_evidence=b_metrics,
                trend_evidence=t_trends,
                risk_evidence=r_risk,
            )

            assert isinstance(report, AnalysisReport)
            assert report.data_source in ["SQLite", "PostgreSQL", "Synthetic Demo Data"]
            assert len(report.all_sections) == 5
            assert report.has_all_sections is True

            # Verify contents include ground truth metrics without invention
            assert "Total Bugs Analyzed" in report.bug_analysis.content
            assert report.executive_summary.content is not None
            assert report.risk_assessment.content is not None

    def test_report_agent_llm_success(self, monkeypatch):
        """Verify ReportAgent incorporates LLM Gateway analysis when available."""
        from unittest.mock import patch

        mock_ai_text = "Technical analysis indicates Authentication component is experiencing token refresh race conditions."
        with patch("backend.llm.gateway.generate_analysis", return_value=mock_ai_text):
            report_agent = ReportAgent()
            report = report_agent.generate_report(
                query="Analyze auth issues",
                bug_evidence={"summary": {"total_bugs": 5, "open_bugs": 2, "critical_high_bugs": 1}},
                risk_evidence={"component_risks": [{"name": "Authentication", "risk_score": 85, "reasons": ["High severity"]}]},
            )

            assert isinstance(report, AnalysisReport)
            assert "AI Evidence-Grounded Synthesis" in report.executive_summary.content
            assert "Authentication" in report.executive_summary.content
            assert report.raw_insights.get("ai_analysis") == mock_ai_text
            assert report.raw_insights.get("llm_generated") is True

    def test_report_agent_llm_unavailable_fallback(self):
        """Verify ReportAgent gracefully falls back to deterministic template when LLM returns None."""
        from unittest.mock import patch

        with patch("backend.llm.gateway.generate_analysis", return_value=None):
            report_agent = ReportAgent()
            report = report_agent.generate_report(
                query="Analyze general bug status",
                bug_evidence={"summary": {"total_bugs": 12, "open_bugs": 4, "critical_high_bugs": 2}},
                trend_evidence={"creation_resolution_trends": [{"period": "2026-01", "created": 10, "resolved": 8}]},
                risk_evidence={"component_risks": [{"name": "Database", "risk_score": 70, "reasons": ["Aging"]}]},
            )

            assert isinstance(report, AnalysisReport)
            assert report.has_all_sections is True
            assert "System analyzed **12** total bugs" in report.executive_summary.content
            assert "Database" in report.executive_summary.content
            assert "ai_analysis" not in report.raw_insights

    def test_report_agent_insufficient_evidence(self):
        """Verify ReportAgent properly handles empty evidence without hallucination."""
        report_agent = ReportAgent()
        report = report_agent.generate_report(
            query="Unknown query with no data",
            bug_evidence={},
            trend_evidence={},
            risk_evidence={},
        )

        assert isinstance(report, AnalysisReport)
        assert "Insufficient data to determine detailed bug analysis" in report.executive_summary.content
        assert report.bug_section if hasattr(report, "bug_section") else report.bug_analysis.is_empty is True
        assert report.raw_insights.get("ai_analysis") is None

    @pytest.mark.asyncio
    async def test_reflection_agent_confirm_valid_answer(self):
        """Verify ReflectionAgent outputs CONFIRM for valid claims matching evidence."""
        async with MCPClient() as client:
            b_metrics = await client.call_tool("get_bug_metrics")
            summary = b_metrics.get("summary", {})

            ref_agent = ReflectionAgent()
            valid_answer = f"Bug Overview: {summary['total_bugs']} total bugs, {summary['open_bugs']} open."

            eval_res, ref_model = ref_agent.reflect(valid_answer, {"summary": summary})

            assert eval_res.verdict == "CONFIRM"
            assert eval_res.quality_score == 1.0
            assert len(eval_res.gaps) == 0
            assert ref_model.is_acceptable is True

    @pytest.mark.asyncio
    async def test_reflection_agent_correct_wrong_answer(self):
        """Verify ReflectionAgent outputs CORRECT and flags discrepancies for wrong numerical claims."""
        async with MCPClient() as client:
            b_metrics = await client.call_tool("get_bug_metrics")
            summary = b_metrics.get("summary", {})

            ref_agent = ReflectionAgent()
            wrong_answer = f"Bug Overview: {summary.get('total_bugs', 0) + 500} total bugs, {summary.get('open_bugs', 0) + 50} open."

            eval_res, ref_model = ref_agent.reflect(wrong_answer, {"summary": summary})

            assert eval_res.verdict == "CORRECT"
            assert eval_res.quality_score < 0.6
            assert len(eval_res.gaps) >= 2
            assert len(eval_res.corrections) >= 2
            assert f"Correct total bugs count to {summary['total_bugs']}." in eval_res.corrections
            assert f"Correct open bugs count to {summary['open_bugs']}." in eval_res.corrections

    @pytest.mark.asyncio
    async def test_reflection_agent_unsupported_claim_detection(self):
        """Verify ReflectionAgent detects unsupported component risk claims."""
        async with MCPClient() as client:
            c_risk = await client.call_tool("get_component_risk")
            comp_list = c_risk.get("component_risks", [])
            true_top_comp = comp_list[0]["name"] if comp_list else "Backend"

            ref_agent = ReflectionAgent()
            unsupported_answer = "Report: Highest risk component 'FakeNonExistentComponent' score 95/100."

            eval_res, _ = ref_agent.reflect(unsupported_answer, {"component_risk": c_risk})

            assert eval_res.verdict == "CORRECT"
            assert any("differ" in gap.lower() or "top risk" in gap.lower() for gap in eval_res.gaps)

    def test_report_agent_empty_query_validation(self):
        """Verify ReportAgent raises ValidationError for empty query."""
        report_agent = ReportAgent()
        with pytest.raises(ValidationError):
            report_agent.generate_report("   ")

    def test_reflection_agent_empty_answer_validation(self):
        """Verify ReflectionAgent raises ValidationError for empty answer."""
        ref_agent = ReflectionAgent()
        with pytest.raises(ValidationError):
            ref_agent.reflect("   ", {})
