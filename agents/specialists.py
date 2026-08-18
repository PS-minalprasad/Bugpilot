"""
BugPilot — Specialist Agents Implementation (Phase 6)
======================================================
Implements BugAnalystAgent, TrendAnalystAgent, and RiskAnalystAgent.
All agents query data strictly via MCPClient -> MCP Server -> MCP Tools.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from agents.base import AgentResult, BaseAgent
from backend.core.exceptions import AgentError, AgentExecutionError, AgentTimeoutError, ValidationError
from mcp_client.client import MCPClient

logger = logging.getLogger("bugpilot.agents")


class BugAnalystAgent(BaseAgent):
    """
    Specialist agent for analyzing bug counts, severity, priority, status,
    unresolved bugs, critical bugs, and reopened bugs.
    """

    def __init__(self, mcp_client: MCPClient, **kwargs: Any) -> None:
        super().__init__(name="Bug Analyst", mcp_client=mcp_client, **kwargs)

    async def run(self, task: str, **kwargs: Any) -> AgentResult:
        if not task or not task.strip():
            raise ValidationError("Task prompt cannot be empty.")

        start_time = time.time()
        tools_used: List[str] = []
        evidence: Dict[str, Any] = {}

        try:
            # Enforce execution timeout
            async with asyncio.timeout(self.timeout_seconds):
                # Ensure connected or trigger connection
                if not self.mcp_client.is_connected:
                    await self.mcp_client.connect()

                discovered = self.mcp_client.discovered_tools

                # Dynamic tool selection matching task focus
                sprint_id = kwargs.get("sprint_id")
                component = kwargs.get("component")
                bug_id = kwargs.get("bug_id")
                query = kwargs.get("query")

                intent = kwargs.get("intent")

                if bug_id and "get_bug" in discovered:
                    res = await self.mcp_client.call_tool("get_bug", {"bug_id": bug_id})
                    tools_used.append("get_bug")
                    evidence["bug_details"] = res

                elif query and "search_bugs" in discovered:
                    res = await self.mcp_client.call_tool("search_bugs", {"query": query, "limit": 5})
                    tools_used.append("search_bugs")
                    evidence["search_results"] = res

                elif not bug_id and not query and intent == "SPECIFIC_BUG":
                    # Fallback to query in task string
                    if "search_bugs" in discovered:
                        res = await self.mcp_client.call_tool("search_bugs", {"query": task, "limit": 5})
                        tools_used.append("search_bugs")
                        evidence["search_results"] = res

                if intent != "SPECIFIC_BUG" and not bug_id and not query:
                    if "get_bug_metrics" in discovered:
                        res = await self.mcp_client.call_tool(
                            "get_bug_metrics",
                            {"sprint_id": sprint_id, "component": component}
                        )
                        tools_used.append("get_bug_metrics")
                        evidence["metrics"] = res

                    if "get_reopened_bugs" in discovered:
                        res = await self.mcp_client.call_tool(
                            "get_reopened_bugs",
                            {"component": component, "limit": 10}
                        )
                        tools_used.append("get_reopened_bugs")
                        evidence["reopened"] = res

                # Formulate structured findings
                if bug_id or query or intent == "SPECIFIC_BUG":
                    bug_obj = evidence.get("bug_details", {}).get("bug")
                    search_list = evidence.get("search_results", [])
                    if isinstance(search_list, dict):
                        search_list = search_list.get("bugs", search_list.get("results", []))

                    b_target = bug_obj or (search_list[0] if search_list else None)

                    if b_target:
                        b_id = str(b_target.get("id") or b_target.get("key") or b_target.get("issue_key") or "N/A")
                        b_title = str(b_target.get("title") or b_target.get("summary") or "N/A")
                        b_status = str(b_target.get("status") or "N/A")
                        b_severity = str(b_target.get("severity") or "N/A")
                        b_priority = str(b_target.get("priority") or "N/A")
                        b_component = str(b_target.get("component") or "N/A")
                        b_assignee = str(b_target.get("assignee") or "Unassigned")
                        b_reporter = str(b_target.get("reporter") or "Unknown")
                        b_desc = str(b_target.get("description") or "No description provided.")

                        from backend.llm.gateway import generate_analysis

                        ai_analysis_text = await generate_analysis(
                            evidence={"bug": b_target, "component": b_component, "description": b_desc},
                            question=task or query or f"Analyze bug {b_id}",
                        )
                        if not ai_analysis_text:
                            ai_analysis_text = (
                                f"The available evidence indicates operational behavior related to {b_component}.\n\n"
                                f"**The available data does not provide enough evidence to determine this.**\n"
                                f"**The available data does not provide enough evidence to confirm the underlying root cause.**"
                            )

                        is_open = b_status.lower() in ["open", "in progress", "reopened"]
                        is_high_sev = b_severity.lower() in ["critical", "high"]
                        risk_level = "High" if (is_open and is_high_sev) else ("Medium" if is_open else "Low")

                        findings = (
                            f"# Bug Analysis Report — {b_id}\n\n"
                            f"## 1. Executive Summary\n\n"
                            f"**{b_id}** is an **{b_status.lower()}, {b_severity.lower()}-severity** issue in the **{b_component}** component. "
                            f"It is classified as **{b_priority.lower()} priority** and assigned to **{b_assignee}**.\n\n"
                            f"## 2. Bug Details\n\n"
                            f"| Field | Value |\n"
                            f"|---|---|\n"
                            f"| **Bug ID** | {b_id} |\n"
                            f"| **Title** | {b_title} |\n"
                            f"| **Status** | {b_status} |\n"
                            f"| **Severity** | {b_severity} |\n"
                            f"| **Priority** | {b_priority} |\n"
                            f"| **Component** | {b_component} |\n"
                            f"| **Assignee** | {b_assignee} |\n"
                            f"| **Reporter** | {b_reporter} |\n\n"
                            f"## 3. Problem Analysis\n\n"
                            f"### Facts\n\n"
                            f"- {b_desc}\n"
                            f"- The affected component is {b_component}.\n\n"
                            f"### AI Analysis\n\n"
                            f"{ai_analysis_text}\n\n"
                            f"## 4. Impact Analysis\n\n"
                            f"The available evidence indicates that operations in component '{b_component}' may experience disruption under trigger conditions.\n\n"
                            f"> **The exact business impact cannot be determined from the available data.**\n"
                            f"> **The exact business impact cannot be determined from the available bug record.**\n\n"
                            f"## 5. Risk Assessment\n\n"
                            f"- **Risk Level:** {risk_level}\n"
                            f"- **Severity:** {b_severity}\n"
                            f"- **Priority:** {b_priority}\n"
                            f"- **Status:** {b_status}\n\n"
                            f"The combination of **{b_severity.lower()} severity**, **{b_priority.lower()} priority**, and an **{b_status.lower()} status** supports prioritizing investigation.\n\n"
                            f"## 6. Historical / Trend Context\n\n"
                            f"> **Historical data was not retrieved for this analysis.**\n\n"
                            f"## 7. Related Issues\n\n"
                            f"> **No related issues were found in the available data.**\n\n"
                            f"## 8. Recommended Investigation\n\n"
                            f"- **Inspect log traces and system metrics for '{b_title}'.**\n"
                            f"- **Reproduce failure conditions in sandbox environment.**\n"
                            f"- **Review code pathways in component '{b_component}'.**\n\n"
                            f"## 9. Final Recommendation\n\n"
                            f"> **Prioritize investigation of {b_id} due to its {b_severity.lower()} severity, {b_priority.lower()} priority, and {b_component} impact.**"
                        )
                    else:
                        search_term = query or bug_id or task
                        findings = f"I couldn't find a bug matching '{search_term}'. Please provide a bug ID or more details."
                else:
                    summary_data = evidence.get("metrics", {}).get("summary", {})
                    breakdowns = evidence.get("metrics", {}).get("breakdowns", {})
                    reopened_data = evidence.get("reopened", {})

                    total_bugs = summary_data.get("total_bugs", 0)
                    open_bugs = summary_data.get("open_bugs", 0)
                    critical_high = summary_data.get("critical_high_bugs", 0)
                    reopened_count = reopened_data.get("count", summary_data.get("reopened_bugs", 0))
                    reopen_rate = summary_data.get("reopen_rate", 0.0)

                    sev_dist = breakdowns.get("by_severity", {})
                    pri_dist = breakdowns.get("by_priority", {})
                    status_dist = breakdowns.get("by_status", {})

                    findings = (
                        f"Bug Analysis Report for task '{task}':\n"
                        f"- Total Bugs analyzed: {total_bugs}\n"
                        f"- Open/Unresolved Bugs: {open_bugs}\n"
                        f"- Critical & High Open Bugs: {critical_high}\n"
                        f"- Reopened Bugs: {reopened_count} (Reopen Rate: {reopen_rate * 100:.1f}%)\n"
                        f"- Severity Distribution: {sev_dist}\n"
                        f"- Priority Distribution: {pri_dist}\n"
                        f"- Status Distribution: {status_dist}"
                    )

                elapsed = time.time() - start_time
                return AgentResult(
                    agent_name=self.name,
                    task=task,
                    status="success",
                    findings=findings,
                    tools_used=tools_used,
                    supporting_evidence=evidence,
                    elapsed_seconds=round(elapsed, 3)
                )

        except asyncio.TimeoutError as err:
            logger.error(f"{self.name} timed out after {self.timeout_seconds}s.")
            raise AgentTimeoutError(f"{self.name} execution timed out.") from err
        except Exception as err:
            logger.error(f"{self.name} execution error: {err}")
            if isinstance(err, (ValidationError, AgentTimeoutError)):
                raise
            raise AgentExecutionError(f"{self.name} failed: {err}") from err


class TrendAnalystAgent(BaseAgent):
    """
    Specialist agent for analyzing creation trends, resolution trends,
    sprint trends, and release trends.
    """

    def __init__(self, mcp_client: MCPClient, **kwargs: Any) -> None:
        super().__init__(name="Trend Analyst", mcp_client=mcp_client, **kwargs)

    async def run(self, task: str, **kwargs: Any) -> AgentResult:
        if not task or not task.strip():
            raise ValidationError("Task prompt cannot be empty.")

        start_time = time.time()
        tools_used: List[str] = []
        evidence: Dict[str, Any] = {}

        try:
            async with asyncio.timeout(self.timeout_seconds):
                if not self.mcp_client.is_connected:
                    await self.mcp_client.connect()

                discovered = self.mcp_client.discovered_tools

                sprint_id = kwargs.get("sprint_id")
                component = kwargs.get("component")

                if "get_bug_trends" in discovered:
                    res = await self.mcp_client.call_tool(
                        "get_bug_trends",
                        {"sprint_id": sprint_id, "component": component}
                    )
                    tools_used.append("get_bug_trends")
                    evidence["trends"] = res

                monthly_trends = evidence.get("trends", {}).get("creation_resolution_trends", [])
                sprint_trends = evidence.get("trends", {}).get("sprint_trends", [])

                total_created_monthly = sum(t.get("created", 0) for t in monthly_trends)
                total_resolved_monthly = sum(t.get("resolved", 0) for t in monthly_trends)

                findings = (
                    f"Trend Analysis Report for task '{task}':\n"
                    f"- Historical Periods Analyzed: {len(monthly_trends)} months, {len(sprint_trends)} sprints\n"
                    f"- Total Created Bugs (Monthly): {total_created_monthly}\n"
                    f"- Total Resolved Bugs (Monthly): {total_resolved_monthly}\n"
                    f"- Recent Monthly Trends: {monthly_trends[-3:] if monthly_trends else []}\n"
                    f"- Recent Sprint Velocity: {sprint_trends[-3:] if sprint_trends else []}"
                )

                elapsed = time.time() - start_time
                return AgentResult(
                    agent_name=self.name,
                    task=task,
                    status="success",
                    findings=findings,
                    tools_used=tools_used,
                    supporting_evidence=evidence,
                    elapsed_seconds=round(elapsed, 3)
                )

        except asyncio.TimeoutError as err:
            logger.error(f"{self.name} timed out after {self.timeout_seconds}s.")
            raise AgentTimeoutError(f"{self.name} execution timed out.") from err
        except Exception as err:
            logger.error(f"{self.name} execution error: {err}")
            if isinstance(err, (ValidationError, AgentTimeoutError)):
                raise
            raise AgentExecutionError(f"{self.name} failed: {err}") from err


class RiskAnalystAgent(BaseAgent):
    """
    Specialist agent for analyzing component risk, release risk,
    critical concentration, aging bugs, and reopened patterns.
    """

    def __init__(self, mcp_client: MCPClient, **kwargs: Any) -> None:
        super().__init__(name="Risk Analyst", mcp_client=mcp_client, **kwargs)

    async def run(self, task: str, **kwargs: Any) -> AgentResult:
        if not task or not task.strip():
            raise ValidationError("Task prompt cannot be empty.")

        start_time = time.time()
        tools_used: List[str] = []
        evidence: Dict[str, Any] = {}

        try:
            async with asyncio.timeout(self.timeout_seconds):
                if not self.mcp_client.is_connected:
                    await self.mcp_client.connect()

                discovered = self.mcp_client.discovered_tools

                component = kwargs.get("component")
                release = kwargs.get("release")

                if "get_component_risk" in discovered:
                    res = await self.mcp_client.call_tool(
                        "get_component_risk",
                        {"component": component}
                    )
                    tools_used.append("get_component_risk")
                    evidence["component_risk"] = res

                if "get_release_risk" in discovered:
                    res = await self.mcp_client.call_tool(
                        "get_release_risk",
                        {"release": release}
                    )
                    tools_used.append("get_release_risk")
                    evidence["release_risk"] = res

                if "get_aging_bugs" in discovered:
                    res = await self.mcp_client.call_tool(
                        "get_aging_bugs",
                        {"min_age_days": 14.0, "limit": 5}
                    )
                    tools_used.append("get_aging_bugs")
                    evidence["aging_bugs"] = res

                comp_risks = evidence.get("component_risk", {}).get("component_risks", [])
                rel_risks = evidence.get("release_risk", {}).get("release_risks", [])
                aging_bugs = evidence.get("aging_bugs", {}).get("aging_bugs", [])

                top_risk_comp = comp_risks[0] if comp_risks else {}
                top_risk_rel = rel_risks[0] if rel_risks else {}

                findings = (
                    f"Risk Analysis Report for task '{task}':\n"
                    f"- Top High-Risk Component: {top_risk_comp.get('name')} (Risk Score: {top_risk_comp.get('risk_score')}/100)\n"
                    f"- Component Risk Drivers: {top_risk_comp.get('reasons', [])}\n"
                    f"- Top High-Risk Release: {top_risk_rel.get('name')} (Risk Score: {top_risk_rel.get('risk_score')}/100)\n"
                    f"- Open Aging Bugs (>14 days count): {len(aging_bugs)}"
                )

                elapsed = time.time() - start_time
                return AgentResult(
                    agent_name=self.name,
                    task=task,
                    status="success",
                    findings=findings,
                    tools_used=tools_used,
                    supporting_evidence=evidence,
                    elapsed_seconds=round(elapsed, 3)
                )

        except asyncio.TimeoutError as err:
            logger.error(f"{self.name} timed out after {self.timeout_seconds}s.")
            raise AgentTimeoutError(f"{self.name} execution timed out.") from err
        except Exception as err:
            logger.error(f"{self.name} execution error: {err}")
            if isinstance(err, (ValidationError, AgentTimeoutError)):
                raise
            raise AgentExecutionError(f"{self.name} failed: {err}") from err
