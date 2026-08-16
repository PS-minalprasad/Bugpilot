"""
BugPilot — Orchestrator Agent Implementation (Phase 7)
======================================================
Coordinates specialist agents and MCP tools in a real agentic loop.
Implements dynamic reasoning over observations to select next tool calls,
respecting max_iterations, execution timeouts, and graceful error handling.
Does NOT expose chain-of-thought internal reasoning.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from agents.base import AgentResult, BaseAgent
from agents.orchestration_models import OrchestrationResult, StepMetadata
from agents.specialists import BugAnalystAgent, RiskAnalystAgent, TrendAnalystAgent
from backend.core.exceptions import AgentError, AgentExecutionError, AgentTimeoutError, ValidationError
from mcp_client.client import MCPClient

from backend.config import settings
from backend.security.prompt_injection import sanitize_untrusted_input, wrap_untrusted_context

logger = logging.getLogger("bugpilot.orchestrator")


class OrchestratorAgent:
    """
    Coordinates execution across Bug Analyst, Trend Analyst, and Risk Analyst specialist agents
    and direct MCP tools in an iterative reasoning loop.
    """

    def __init__(
        self,
        mcp_client: MCPClient,
        max_iterations: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.name = "Orchestrator Agent"
        self.mcp_client = mcp_client
        self.max_iterations = max_iterations or settings.MAX_AGENT_STEPS
        self.timeout_seconds = timeout_seconds or settings.TOOL_TIMEOUT_SECONDS

        self.bug_analyst = BugAnalystAgent(mcp_client=mcp_client)
        self.trend_analyst = TrendAnalystAgent(mcp_client=mcp_client)
        self.risk_analyst = RiskAnalystAgent(mcp_client=mcp_client)

    def _classify_intent(self, query: str) -> Dict[str, Any]:
        """
        Classifies user query based on requested outcome:
        - SPECIFIC_BUG: "status of BP-101", "details of login bug"
        - BUG_SEARCH: "search for all open billing bugs", "find critical severity bugs"
        - METRIC: "how many bugs are open?", "how many total bugs do we have?"
        - TREND: "what is the current bug trend?", "are authentication bugs increasing?"
        - REOPENED_BUGS: "which bugs were reopened?", "reopened bug list"
        - COMPONENT_ANALYSIS / RISK: "which component has highest risk?", "component risk for Authentication"
        - RELEASE_RISK: "is the upcoming release safe?", "release readiness"
        - AGING_BUGS: "show me old unresolved bugs", "aging tickets"
        - GENERAL_REPORT: "give me a complete engineering health report"
        """
        q_lower = query.lower().strip()

        # 1. Explicit Issue Key Lookups -> SPECIFIC_BUG
        key_match = re.search(r'\b([A-Za-z]+-\d+)\b', query)
        if key_match:
            return {
                "intent": "SPECIFIC_BUG",
                "bug_id": key_match.group(1),
                "search_term": key_match.group(1),
            }

        # Multi-domain / Composite Report query triggers (checked before single domains)
        has_risk = any(k in q_lower for k in ["risk", "risks", "hazard", "threat", "aging", "dangerous", "release", "safe"])
        has_metrics = any(k in q_lower for k in ["metric", "metrics", "count", "severity", "summary", "how many", "open bugs", "total bugs"])
        has_trends = any(k in q_lower for k in ["trend", "trends", "history", "velocity", "increasing", "decreasing", "reopen", "reopened", "ago"])

        if (has_risk and has_metrics) or (has_risk and has_trends) or (has_metrics and has_trends) or any(k in q_lower for k in ["health report", "complete report", "executive report", "full report", "overall report", "system report", "summary report", "overall"]):
            return {"intent": "REPORT", "bug_id": None, "search_term": None}

        # 2. Release Risk Evaluation
        if any(w in q_lower for w in ["release safe", "release risk", "safe to deploy", "can we deploy", "release readiness", "deploy risk", "upcoming release"]):
            return {"intent": "RELEASE_RISK", "bug_id": None, "search_term": None}

        # 3. Aging Bugs Evaluation
        if any(w in q_lower for w in ["aging", "old bug", "old unresolved", "stagnant", "older than", "old tickets"]):
            return {"intent": "AGING_BUGS", "bug_id": None, "search_term": None}

        # 4. Reopened Bugs Evaluation
        if any(w in q_lower for w in ["reopen", "reopened", "re-open", "re-opened", "multiple times"]):
            return {"intent": "REOPENED_BUGS", "bug_id": None, "search_term": None}

        # 5. Component Risk Analysis
        if any(w in q_lower for w in ["component risk", "highest risk", "most risky", "riskiest", "component danger", "module risk"]):
            return {"intent": "COMPONENT_ANALYSIS", "bug_id": None, "search_term": None}

        # 6. Time-Series Trends
        if any(w in q_lower for w in ["trend", "trends", "increasing", "decreasing", "velocity", "historical", "over time", "history"]):
            return {"intent": "TREND", "bug_id": None, "search_term": None}

        # 7. Bug Search Queries
        if any(q_lower.startswith(w) for w in ["search", "find", "list all", "filter"]) or ("search for" in q_lower or "find all" in q_lower or "find critical" in q_lower):
            words = [w for w in q_lower.split() if w not in ["search", "find", "for", "all", "open", "in", "project", "bugs", "bug", "issues", "issue"]]
            clean_term = " ".join(words) if words else q_lower
            return {"intent": "BUG_SEARCH", "bug_id": None, "search_term": clean_term}

        # 8. General Metrics
        if any(w in q_lower for w in ["how many", "count", "metric", "metrics", "total bugs", "open bugs", "severity breakdown", "distribution", "breakdown"]):
            return {"intent": "METRIC", "bug_id": None, "search_term": None}

        # 9. General Risk
        if has_risk:
            return {"intent": "RISK", "bug_id": None, "search_term": None}

        # 10. Specific Bug Lookups by Phrase
        specific_triggers = ["tell me about", "details of", "status of", "info on", "login bug", "authentication bug", "auth bug", "show me details", "details for", "show details for", "details", "root cause"]
        if any(trigger in q_lower for trigger in specific_triggers):
            term = q_lower
            for prefix in ["tell me about my", "tell me about the", "tell me about", "show me details of", "show details for", "details of", "status of", "info on", "show details", "details for", "what is the exact confirmed root cause of"]:
                if prefix in term:
                    term = term.split(prefix)[-1].strip()
                    break
            words = [w for w in term.split() if w not in ["bug", "issue", "details", "for", "the", "my", "a", "an", "show", "of", "exact", "confirmed", "root", "cause", "what", "is"]]
            clean_term = " ".join(words) if words else term
            return {
                "intent": "SPECIFIC_BUG",
                "bug_id": None,
                "search_term": clean_term,
            }

        # Fallback check for specific bug feature terms or search
        if any(w in q_lower for w in ["login", "auth", "authentication", "ui", "api", "database", "token", "password", "billing", "payment"]):
            words = [w for w in q_lower.split() if w not in ["tell", "me", "about", "the", "my", "a", "an", "bug", "bugs", "issue", "issues", "what", "is", "status", "show", "details", "for", "all", "open", "in", "project"]]
            search_term = " ".join(words) if words else q_lower
            return {"intent": "SPECIFIC_BUG", "bug_id": None, "search_term": search_term}

        return {"intent": "METRIC", "bug_id": None, "search_term": None}

    async def run(self, user_query: str, **kwargs: Any) -> OrchestrationResult:
        if not user_query or not user_query.strip():
            raise ValidationError("User query cannot be empty.")

        # Guardrail 7: Validate & bound query length
        if len(user_query) > settings.MAX_USER_QUERY_LENGTH:
            raise ValidationError(f"User query exceeds maximum length of {settings.MAX_USER_QUERY_LENGTH} characters.")

        # Guardrail 3: Sanitize prompt injection attempts in user query
        sanitized_query = sanitize_untrusted_input(user_query, max_length=settings.MAX_USER_QUERY_LENGTH)

        start_wall_time = time.time()
        execution_id = str(uuid.uuid4())
        execution_steps: List[StepMetadata] = []
        observations: Dict[str, Any] = {}
        tool_call_count = 0

        # Classify query intent
        classified = self._classify_intent(sanitized_query)
        intent = classified["intent"]
        bug_id_param = classified["bug_id"] or kwargs.get("bug_id")
        search_term_param = classified["search_term"] or kwargs.get("query")

        try:
            async with asyncio.timeout(self.timeout_seconds):
                if not self.mcp_client.is_connected:
                    await self.mcp_client.connect()

                discovered = self.mcp_client.discovered_tools
                if not discovered:
                    await self.mcp_client.discover_tools()
                    discovered = self.mcp_client.discovered_tools

                iteration = 0
                is_complete = False

                effective_max_steps = min(self.max_iterations, settings.MAX_AGENT_STEPS)

                while iteration < effective_max_steps and not is_complete:
                    if tool_call_count >= settings.MAX_MCP_TOOL_CALLS:
                        logger.warning(f"Reached MAX_MCP_TOOL_CALLS ({settings.MAX_MCP_TOOL_CALLS}). Stopping agent loop.")
                        break
                    iteration += 1
                    step_start = time.time()

                    selected_tool: Optional[str] = None
                    tool_args: Dict[str, Any] = {}
                    agent_role = "Orchestrator Agent"

                    # 1. Specific Bug Intent
                    if intent == "SPECIFIC_BUG":
                        if bug_id_param and "get_bug" in discovered and "get_bug" not in observations:
                            selected_tool = "get_bug"
                            tool_args = {"bug_id": bug_id_param}
                            agent_role = "Bug Analyst"
                        elif "search_bugs" in discovered and "search_bugs" not in observations:
                            selected_tool = "search_bugs"
                            tool_args = {"query": search_term_param or sanitized_query, "limit": 5}
                            agent_role = "Bug Analyst"

                    # 2. Bug Search Intent
                    elif intent == "BUG_SEARCH":
                        if "search_bugs" in discovered and "search_bugs" not in observations:
                            selected_tool = "search_bugs"
                            tool_args = {"query": search_term_param or sanitized_query, "limit": 10}
                            agent_role = "Bug Analyst"

                    # 3. Metrics Intent
                    elif intent in ["METRIC", "METRICS"]:
                        if "get_bug_metrics" not in observations and "get_bug_metrics" in discovered:
                            selected_tool = "get_bug_metrics"
                            tool_args = {"sprint_id": kwargs.get("sprint_id"), "component": kwargs.get("component")}
                            agent_role = "Bug Analyst"

                    # 4. Trend Intent
                    elif intent == "TREND":
                        if "get_bug_trends" not in observations and "get_bug_trends" in discovered:
                            selected_tool = "get_bug_trends"
                            tool_args = {"sprint_id": kwargs.get("sprint_id"), "component": kwargs.get("component")}
                            agent_role = "Trend Analyst"

                    # 5. Reopened Bugs Intent
                    elif intent == "REOPENED_BUGS":
                        if "get_reopened_bugs" not in observations and "get_reopened_bugs" in discovered:
                            selected_tool = "get_reopened_bugs"
                            tool_args = {"component": kwargs.get("component"), "limit": 10}
                            agent_role = "Trend Analyst"

                    # 6. Component Risk / Risk Intent
                    elif intent in ["RISK", "COMPONENT_ANALYSIS"]:
                        if "get_component_risk" not in observations and "get_component_risk" in discovered:
                            selected_tool = "get_component_risk"
                            tool_args = {"component": kwargs.get("component")}
                            agent_role = "Risk Analyst"

                    # 7. Release Risk Intent
                    elif intent == "RELEASE_RISK":
                        if "get_release_risk" not in observations and "get_release_risk" in discovered:
                            selected_tool = "get_release_risk"
                            tool_args = {"sprint_id": kwargs.get("sprint_id")}
                            agent_role = "Risk Analyst"
                        elif "get_component_risk" not in observations and "get_component_risk" in discovered:
                            selected_tool = "get_component_risk"
                            tool_args = {"component": kwargs.get("component")}
                            agent_role = "Risk Analyst"

                    # 8. Aging Bugs Intent
                    elif intent == "AGING_BUGS":
                        if "get_aging_bugs" not in observations and "get_aging_bugs" in discovered:
                            selected_tool = "get_aging_bugs"
                            tool_args = {"min_age_days": 14.0, "limit": 10}
                            agent_role = "Risk Analyst"

                    # 9. General Report / Composite Intent
                    elif intent in ["REPORT", "GENERAL_REPORT"]:
                        if "get_bug_metrics" not in observations and "get_bug_metrics" in discovered:
                            selected_tool = "get_bug_metrics"
                            tool_args = {"sprint_id": kwargs.get("sprint_id"), "component": kwargs.get("component")}
                            agent_role = "Bug Analyst"
                        elif "get_component_risk" not in observations and "get_component_risk" in discovered:
                            selected_tool = "get_component_risk"
                            tool_args = {"component": kwargs.get("component")}
                            agent_role = "Risk Analyst"
                        elif "get_bug_trends" not in observations and "get_bug_trends" in discovered:
                            selected_tool = "get_bug_trends"
                            tool_args = {"sprint_id": kwargs.get("sprint_id"), "component": kwargs.get("component")}
                            agent_role = "Trend Analyst"

                    # Fallback
                    if not selected_tool:
                        if "get_bug_metrics" not in observations and intent != "SPECIFIC_BUG":
                            selected_tool = "get_bug_metrics"
                            tool_args = {"sprint_id": kwargs.get("sprint_id"), "component": kwargs.get("component")}
                            agent_role = "Bug Analyst"
                        else:
                            break

                    # Execute selected tool via MCP Client
                    tool_call_count += 1
                    tool_res = await self.mcp_client.call_tool(selected_tool, tool_args)
                    step_duration = time.time() - step_start

                    # Record observation
                    observations[selected_tool] = tool_res

                    # Summarize step result for metadata
                    if selected_tool == "get_bug":
                        b_res = tool_res.get("bug")
                        res_summary = f"Retrieved bug details for '{b_res.get('id', b_res.get('key'))}'." if b_res else f"No bug found for ID '{bug_id_param}'."
                    elif selected_tool == "search_bugs":
                        search_bugs_list = tool_res if isinstance(tool_res, list) else tool_res.get("bugs", tool_res.get("results", []))
                        res_summary = f"Found {len(search_bugs_list)} matching bugs for query '{search_term_param or sanitized_query}'."
                    elif selected_tool == "get_bug_metrics":
                        summary_info = tool_res.get("summary", {})
                        res_summary = (
                            f"Retrieved bug metrics: {summary_info.get('total_bugs', 0)} total, "
                            f"{summary_info.get('open_bugs', 0)} open, {summary_info.get('critical_high_bugs', 0)} critical/high."
                        )
                    elif selected_tool == "get_component_risk":
                        count = tool_res.get("count", 0)
                        res_summary = f"Retrieved component risk scores for {count} components."
                    elif selected_tool == "get_release_risk":
                        count = tool_res.get("count", 0)
                        res_summary = f"Retrieved release risk scores for {count} releases."
                    elif selected_tool == "get_bug_trends":
                        trends_count = len(tool_res.get("creation_resolution_trends", []))
                        res_summary = f"Retrieved trend history for {trends_count} periods."
                    elif selected_tool == "get_aging_bugs":
                        count = tool_res.get("count", 0)
                        res_summary = f"Retrieved {count} open aging bugs."
                    elif selected_tool == "get_reopened_bugs":
                        count = tool_res.get("count", 0)
                        res_summary = f"Retrieved {count} reopened bugs."
                    else:
                        res_summary = f"Executed tool '{selected_tool}' successfully."

                    # Record clean step metadata
                    step_meta = StepMetadata(
                        execution_id=execution_id,
                        step_number=iteration,
                        agent_name=agent_role,
                        tool_name=selected_tool,
                        intent=intent,
                        status="success",
                        result_summary=res_summary,
                        duration_seconds=round(step_duration, 3),
                    )
                    execution_steps.append(step_meta)

                    # Dynamic Termination Evaluation
                    if intent in ["SPECIFIC_BUG", "BUG_SEARCH"] and ("get_bug" in observations or "search_bugs" in observations):
                        is_complete = True
                    elif intent in ["METRIC", "METRICS"] and "get_bug_metrics" in observations:
                        is_complete = True
                    elif intent == "TREND" and "get_bug_trends" in observations:
                        is_complete = True
                    elif intent == "REOPENED_BUGS" and "get_reopened_bugs" in observations:
                        is_complete = True
                    elif intent in ["RISK", "COMPONENT_ANALYSIS"] and "get_component_risk" in observations:
                        is_complete = True
                    elif intent == "RELEASE_RISK" and ("get_release_risk" in observations or "get_component_risk" in observations):
                        is_complete = True
                    elif intent == "AGING_BUGS" and "get_aging_bugs" in observations:
                        is_complete = True
                    elif intent in ["REPORT", "GENERAL_REPORT"] and "get_bug_metrics" in observations and "get_component_risk" in observations and "get_bug_trends" in observations:
                        is_complete = True

                # Formulate Evidence-Grounded Final Response
                if intent in ["SPECIFIC_BUG", "BUG_SEARCH"]:
                    bug_analyst_res = await self.bug_analyst.run(
                        sanitized_query,
                        bug_id=bug_id_param,
                        query=search_term_param,
                        intent=intent,
                    )
                    final_answer = bug_analyst_res.findings
                elif intent == "REOPENED_BUGS" and "get_reopened_bugs" in observations:
                    from backend.llm.gemini_client import generate_analysis

                    reopened_data = observations["get_reopened_bugs"]
                    count = reopened_data.get("count", 0)
                    reopened_bugs = reopened_data.get("reopened_bugs", [])

                    ai_analysis_text = await generate_analysis(
                        evidence={"reopened_bugs": reopened_bugs, "count": count},
                        question=user_query,
                    )
                    if not ai_analysis_text:
                        ai_analysis_text = "Reopened bugs indicate potential test coverage gaps or regressions."

                    final_answer = (
                        f"# Reopened Bugs Analysis\n\n"
                        f"## 1. Executive Summary\n\n"
                        f"Found **{count} reopened bugs** in active data.\n\n"
                        f"## 2. Problem Analysis\n\n"
                        f"### Facts\n\n"
                        f"- Total reopened bugs retrieved: {count}\n\n"
                        f"### AI Analysis\n\n"
                        f"{ai_analysis_text}\n\n"
                        f"## 3. Recommended Investigation\n\n"
                        f"- Review root causes for bugs with multiple reopen cycles.\n"
                    )
                elif intent == "AGING_BUGS" and "get_aging_bugs" in observations:
                    from backend.llm.gemini_client import generate_analysis

                    aging_data = observations["get_aging_bugs"]
                    count = aging_data.get("count", 0)

                    ai_analysis_text = await generate_analysis(
                        evidence=aging_data,
                        question=user_query,
                    )
                    if not ai_analysis_text:
                        ai_analysis_text = "Stagnant bugs can accumulate technical debt and introduce latent delivery risk."

                    final_answer = (
                        f"# Aging Bugs Analysis\n\n"
                        f"## 1. Executive Summary\n\n"
                        f"Found **{count} unresolved aging bugs** exceeding aging threshold.\n\n"
                        f"## 2. Problem Analysis\n\n"
                        f"### Facts\n\n"
                        f"- Aging bugs retrieved: {count}\n\n"
                        f"### AI Analysis\n\n"
                        f"{ai_analysis_text}\n\n"
                        f"## 3. Recommended Investigation\n\n"
                        f"- Prioritize triage and resolution of oldest open tickets.\n"
                    )
                elif intent == "RELEASE_RISK" and ("get_release_risk" in observations or "get_component_risk" in observations):
                    from backend.llm.gemini_client import generate_analysis

                    ai_analysis_text = await generate_analysis(
                        evidence={
                            "release_risk": observations.get("get_release_risk"),
                            "component_risk": observations.get("get_component_risk"),
                        },
                        question=user_query,
                    )
                    if not ai_analysis_text:
                        ai_analysis_text = "Release safety depends on resolving open critical/high blockers before final deployment."

                    final_answer = (
                        f"# Release Risk Evaluation\n\n"
                        f"## 1. Executive Summary\n\n"
                        f"Evaluated release safety and risk exposure across active components.\n\n"
                        f"## 2. Risk Assessment\n\n"
                        f"### Facts\n\n"
                        f"- Release risk metrics retrieved via MCP tools.\n\n"
                        f"### AI Analysis\n\n"
                        f"{ai_analysis_text}\n\n"
                        f"## 3. Final Recommendation\n\n"
                        f"> **Review open blocker issues prior to deployment sign-off.**\n"
                    )
                elif intent in ["RISK", "COMPONENT_ANALYSIS"] and "get_component_risk" in observations:
                    from backend.llm.gemini_client import generate_analysis

                    comps = observations["get_component_risk"].get("component_risks", [])
                    top_name = comps[0].get("name") if comps else "None"
                    top_score = comps[0].get("risk_score") if comps else 0

                    ai_analysis_text = await generate_analysis(
                        evidence={
                            "components": comps,
                            "highest_risk": top_name,
                            "risk_score": top_score,
                        },
                        question=user_query,
                    )
                    if not ai_analysis_text:
                        ai_analysis_text = f"Component risk reflects severity, age, and open bug volume in {top_name}."

                    final_answer = (
                        f"# Component Risk Analysis\n\n"
                        f"## 1. Executive Summary\n\n"
                        f"Highest risk component identified as **{top_name}** with risk score **{top_score}/100**.\n\n"
                        f"## 2. Risk Assessment\n\n"
                        f"### Facts\n\n"
                        f"- Evaluated {len(comps)} components via MCP.\n"
                        f"- Highest risk component: {top_name} ({top_score}/100).\n\n"
                        f"### AI Analysis\n\n"
                        f"{ai_analysis_text}\n\n"
                        f"## 3. Recommended Investigation\n\n"
                        f"- Review open critical issues in '{top_name}'.\n"
                    )
                else:
                    final_parts = [f"Orchestrated analysis for query: '{user_query}'"]
                    if "get_bug_metrics" in observations:
                        s = observations["get_bug_metrics"].get("summary", {})
                        final_parts.append(
                            f"- Bug Summary: Total {s.get('total_bugs', 0)} bugs, {s.get('open_bugs', 0)} open, "
                            f"{s.get('critical_high_bugs', 0)} critical/high priority."
                        )
                    if "get_component_risk" in observations:
                        comps = observations["get_component_risk"].get("component_risks", [])
                        if comps:
                            top = comps[0]
                            final_parts.append(
                                f"- Component Risk: Highest risk component '{top.get('name')}' (score {top.get('risk_score')}/100)."
                            )
                    if "get_bug_trends" in observations:
                        t = observations["get_bug_trends"].get("creation_resolution_trends", [])
                        final_parts.append(f"- Trend Analysis: Analyzed {len(t)} historical periods.")

                    final_answer = "\n".join(final_parts)

                elapsed_total = time.time() - start_wall_time

                return OrchestrationResult(
                    execution_id=execution_id,
                    user_query=user_query,
                    intent=intent,
                    status="success",
                    final_answer=final_answer,
                    total_steps=len(execution_steps),
                    execution_steps=execution_steps,
                    elapsed_seconds=round(elapsed_total, 3),
                )

        except asyncio.TimeoutError as err:
            logger.error(f"Orchestrator timed out after {self.timeout_seconds}s.")
            raise AgentTimeoutError(f"Orchestrator execution timed out after {self.timeout_seconds}s.") from err
        except Exception as err:
            logger.error(f"Orchestrator execution error: {err}")
            if isinstance(err, (ValidationError, AgentTimeoutError)):
                raise
            raise AgentExecutionError(f"Orchestrator execution failed: {err}") from err
