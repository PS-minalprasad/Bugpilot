"""
BugPilot — Report Agent & Reflection Agent (Phase 8)
======================================================
Report Agent: Synthesizes structured AnalysisReport strictly from retrieved MCP evidence.
Reflection Agent: Validates claims and numerical metrics against evidence, returning CONFIRM or CORRECT.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.core.exceptions import AgentError, AgentExecutionError, ValidationError
from models.report import AnalysisReport, ReflectionResult, ReportSection

logger = logging.getLogger("bugpilot.report_reflection")


class ReportAgent:
    """
    Report Agent synthesizes findings from Bug, Trend, and Risk analyst evidence
    into a structured engineering report (AnalysisReport) without inventing metrics.
    """

    def __init__(self) -> None:
        self.name = "Report Agent"

    def generate_report(
        self,
        query: str,
        bug_evidence: Optional[Dict[str, Any]] = None,
        trend_evidence: Optional[Dict[str, Any]] = None,
        risk_evidence: Optional[Dict[str, Any]] = None,
        analysis_id: Optional[str] = None,
    ) -> AnalysisReport:
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty for report generation.")

        analysis_id = analysis_id or f"analysis-{uuid.uuid4().hex[:8]}"
        report_id = f"report-{uuid.uuid4().hex[:8]}"

        b_ev = bug_evidence or {}
        t_ev = trend_evidence or {}
        r_ev = risk_evidence or {}

        # 1. Bug Analysis Section
        summary_m = b_ev.get("summary", {}) or b_ev.get("metrics", {}).get("summary", {})
        total_bugs = summary_m.get("total_bugs", 0)
        open_bugs = summary_m.get("open_bugs", 0)
        resolved_bugs = summary_m.get("resolved_bugs", 0)
        crit_high = summary_m.get("critical_high_bugs", 0)

        bug_content = (
            f"### Bug Distribution & Status Metrics\n"
            f"- **Total Bugs Analyzed**: {total_bugs}\n"
            f"- **Open / Unresolved Bugs**: {open_bugs}\n"
            f"- **Resolved Bugs**: {resolved_bugs}\n"
            f"- **Critical & High Open Bugs**: {crit_high}\n"
            f"- **Data Source**: Synthetic Demo Data"
        )
        bug_section = ReportSection(
            title="Bug Analysis",
            content=bug_content,
            confidence=1.0 if summary_m else 0.5,
            is_empty=not bool(summary_m)
        )

        # 2. Trend Analysis Section
        trends_m = t_ev.get("creation_resolution_trends", []) or t_ev.get("trends", {}).get("creation_resolution_trends", [])
        sprints_m = t_ev.get("sprint_trends", []) or t_ev.get("trends", {}).get("sprint_trends", [])

        trend_content = (
            f"### Creation vs. Resolution Trends\n"
            f"- **Historical Monthly Periods Analyzed**: {len(trends_m)}\n"
            f"- **Historical Sprints Analyzed**: {len(sprints_m)}\n"
            f"- **Recent Monthly History**: {trends_m[-3:] if trends_m else 'No trend metrics retrieved'}\n"
            f"- **Recent Sprint Velocity**: {sprints_m[-3:] if sprints_m else 'No sprint metrics retrieved'}"
        )
        trend_section = ReportSection(
            title="Trend Analysis",
            content=trend_content,
            confidence=1.0 if trends_m or sprints_m else 0.5,
            is_empty=not bool(trends_m or sprints_m)
        )

        # 3. Risk Assessment Section
        comp_r = r_ev.get("component_risks", []) or r_ev.get("component_risk", {}).get("component_risks", [])
        rel_r = r_ev.get("release_risks", []) or r_ev.get("release_risk", {}).get("release_risks", [])
        aging_b = r_ev.get("aging_bugs", []) or r_ev.get("aging_bugs", {}).get("aging_bugs", [])

        top_comp = comp_r[0] if comp_r else {}
        top_rel = rel_r[0] if rel_r else {}

        risk_content = (
            f"### Hotspot & Risk Assessment\n"
            f"- **Top High-Risk Component**: {top_comp.get('name', 'N/A')} (Risk Score: {top_comp.get('risk_score', 0)}/100)\n"
            f"- **Risk Drivers**: {', '.join(top_comp.get('reasons', ['None']))}\n"
            f"- **Top High-Risk Release**: {top_rel.get('name', 'N/A')} (Risk Score: {top_rel.get('risk_score', 0)}/100)\n"
            f"- **Open Aging Bugs (>14 days)**: {len(aging_b)}"
        )
        risk_section = ReportSection(
            title="Risk Assessment",
            content=risk_content,
            confidence=1.0 if comp_r or rel_r else 0.5,
            is_empty=not bool(comp_r or rel_r)
        )

        # 4. Executive Summary Section
        if not summary_m and not comp_r and not trends_m:
            exec_content = (
                f"Executive Summary for Query: *\"{query}\"*\n\n"
                f"Insufficient data to determine detailed bug analysis. No relevant MCP tool observations were retrieved for this query."
            )
        else:
            exec_content = (
                f"Executive Summary for Query: *\"{query}\"*\n\n"
                f"System analyzed **{total_bugs}** total bugs (**{open_bugs}** open, **{crit_high}** critical/high severity). "
                f"Highest risk is concentrated in component **{top_comp.get('name', 'N/A')}** (Risk Score: {top_comp.get('risk_score', 0)}/100)."
            )
        exec_section = ReportSection(
            title="Executive Summary",
            content=exec_content,
            confidence=min(bug_section.confidence, risk_section.confidence) if (summary_m or comp_r) else 0.0,
            is_empty=not bool(summary_m or comp_r)
        )

        # 5. Recommendations Section
        recs_content = (
            f"### Actionable Recommendations\n"
            f"1. Prioritize resolution of the {crit_high} open Critical/High bugs in high-risk component '{top_comp.get('name', 'N/A')}'.\n"
            f"2. Conduct targeted code quality review on top risk component '{top_comp.get('name', 'N/A')}'.\n"
            f"3. Address {len(aging_b)} aging open bugs exceeding SLA thresholds."
        )
        recs_section = ReportSection(
            title="Recommendations",
            content=recs_content,
            confidence=0.9,
            is_empty=False
        )

        return AnalysisReport(
            report_id=report_id,
            analysis_id=analysis_id,
            generated_at=datetime.utcnow(),
            data_source="Synthetic Demo Data",
            executive_summary=exec_section,
            bug_analysis=bug_section,
            trend_analysis=trend_section,
            risk_assessment=risk_section,
            recommendations=recs_section,
            raw_insights={"bug": b_ev, "trend": t_ev, "risk": r_ev}
        )


class ReflectionEvaluation(BaseModel):
    """Evaluation output schema from Reflection Agent."""
    verdict: str = Field(..., description="CONFIRM or CORRECT")
    quality_score: float = Field(..., ge=0.0, le=1.0)
    gaps: List[str] = Field(default_factory=list)
    corrections: List[str] = Field(default_factory=list)
    corrected_answer: Optional[str] = None


class ReflectionAgent:
    """
    Reflection Agent validates answers and claims against ground-truth evidence.
    Returns verdict CONFIRM if valid, or CORRECT if wrong/unsupported numerical conclusions are present.
    """

    def __init__(self) -> None:
        self.name = "Reflection Agent"

    def reflect(
        self,
        answer: str,
        evidence: Dict[str, Any],
        report_id: str = "report-test"
    ) -> Tuple[ReflectionEvaluation, ReflectionResult]:
        if not answer or not answer.strip():
            raise ValidationError("Answer to reflect upon cannot be empty.")

        gaps: List[str] = []
        corrections: List[str] = []
        is_valid = True

        # Extract evidence ground truth
        metrics = evidence.get("metrics", {}) or evidence.get("bug", {}).get("metrics", {})
        summary = metrics.get("summary", {}) or evidence.get("summary", {})
        bug_obj = evidence.get("bug_details", {}).get("bug") or evidence.get("bug")
        search_results = evidence.get("search_results", [])
        if isinstance(search_results, dict):
            search_results = search_results.get("bugs", search_results.get("results", []))

        # 1. Validate Specific Bug Queries
        if bug_obj or search_results:
            target_bug = bug_obj or (search_results[0] if search_results else None)
            if target_bug:
                expected_id = str(target_bug.get("id", target_bug.get("key", "")))
                if expected_id and expected_id.lower() not in answer.lower():
                    is_valid = False
                    gaps.append(f"Answer does not mention the retrieved target bug ID '{expected_id}'.")
                    corrections.append(f"Discuss specific bug details for ID '{expected_id}'.")

        # 2. Check Missing Bug Response grounding
        if evidence.get("intent") == "SPECIFIC_BUG" and not bug_obj and not search_results:
            if "couldn't find a bug" not in answer.lower() and "could not find" not in answer.lower() and "no bug found" not in answer.lower():
                is_valid = False
                gaps.append("User requested a specific bug but no match exists; answer failed to clearly inform user.")
                corrections.append("State clearly that no matching bug was found.")

        # 3. Validate numerical total_bugs claims if total_bugs is mentioned
        true_total = summary.get("total_bugs")
        true_open = summary.get("open_bugs")

        if true_total is not None:
            match = re.search(r"(\d+)\s*(?:total bugs|total)", answer, re.IGNORECASE)
            if match:
                claimed_val = int(match.group(1))
                if claimed_val != true_total:
                    is_valid = False
                    err = f"Claimed total bugs ({claimed_val}) does not match ground truth evidence ({true_total})."
                    gaps.append(err)
                    corrections.append(f"Correct total bugs count to {true_total}.")

        # 4. Validate open_bugs claims
        if true_open is not None:
            match = re.search(r"(\d+)\s*open", answer, re.IGNORECASE)
            if match:
                claimed_val = int(match.group(1))
                if claimed_val != true_open:
                    is_valid = False
                    err = f"Claimed open bugs ({claimed_val}) does not match ground truth evidence ({true_open})."
                    gaps.append(err)
                    corrections.append(f"Correct open bugs count to {true_open}.")

        # 5. Check for unsupported high risk component claims
        comp_risks = evidence.get("component_risk", {}).get("component_risks", []) or evidence.get("risk", {}).get("component_risks", [])
        if comp_risks:
            true_top_comp = comp_risks[0].get("name")
            comp_match = re.search(r"highest risk component ['\"]?(\w+)['\"]?", answer, re.IGNORECASE)
            if comp_match:
                claimed_comp = comp_match.group(1)
                if true_top_comp and claimed_comp.lower() != true_top_comp.lower():
                    is_valid = False
                    err = f"Claimed top risk component '{claimed_comp}' differs from evidence top risk '{true_top_comp}'."
                    gaps.append(err)
                    corrections.append(f"Correct top risk component to '{true_top_comp}'.")

        # Calculate 6-Dimension Weighted Quality Score
        rel_score = 1.0 if not gaps else 0.70
        ground_score = 1.0 if is_valid else 0.40
        corr_score = 1.0 if not gaps else max(0.20, 1.0 - (len(gaps) * 0.25))
        comp_score = 1.0 if any(sec in answer for sec in ["Executive Summary", "Bug Details", "Problem Analysis", "Risk Assessment"]) else 0.70
        act_score = 1.0 if "Recommend" in answer or "Investigat" in answer or "Prioritize" in answer else 0.50
        fmt_score = 1.0 if any(sym in answer for sym in ["# ", "## ", "|", "- ", "> "]) else 0.60

        weighted_score = round(
            (0.20 * rel_score) +
            (0.25 * ground_score) +
            (0.20 * corr_score) +
            (0.15 * comp_score) +
            (0.10 * act_score) +
            (0.10 * fmt_score),
            2
        )

        if is_valid and not gaps:
            verdict = "CONFIRM"
            quality_score = 1.0
            critique = "Answer accurately reflects ground-truth evidence with excellent structure and formatting."
            corrected_ans = None
        else:
            verdict = "CORRECT"
            quality_score = min(0.55, weighted_score)
            critique = f"Answer contains discrepancies or missing information: {'; '.join(gaps)}"
            corrected_ans = answer
            if true_total is not None:
                corrected_ans = re.sub(r"(\d+)\s*(?:total bugs|total)", f"{true_total} total bugs", corrected_ans, flags=re.IGNORECASE)
            if true_open is not None:
                corrected_ans = re.sub(r"(\d+)\s*open", f"{true_open} open", corrected_ans, flags=re.IGNORECASE)

        eval_result = ReflectionEvaluation(
            verdict=verdict,
            quality_score=quality_score,
            gaps=gaps,
            corrections=corrections,
            corrected_answer=corrected_ans
        )

        result_model = ReflectionResult(
            reflection_id=f"reflection-{uuid.uuid4().hex[:8]}",
            report_id=report_id,
            generated_at=datetime.utcnow(),
            quality_score=quality_score,
            gaps=gaps,
            follow_up_questions=["Are there specific components requiring SLA exception review?"] if not is_valid else [],
            critique=critique,
            reflection_confidence=1.0
        )

        return eval_result, result_model
