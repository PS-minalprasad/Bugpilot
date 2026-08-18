"""
BugPilot — LLM & ReAct Prompts
================================
Houses system prompts, user prompt builders, and report analysis prompts.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def build_react_system_prompt() -> str:
    """Returns the ReAct system instructions enforcing strict JSON output and iterative multi-step reasoning."""
    return (
        "You are the BugPilot ReAct Orchestrator Agent. Your job is to iteratively solve "
        "the user's engineering bug intelligence goal by dynamically selecting MCP tools, "
        "delegating to specialist agents, or finishing when sufficient evidence is collected.\n\n"
        "REASONING PROTOCOL & MULTI-STEP INVESTIGATION GUIDELINES:\n"
        "1. Inspect the USER GOAL, AVAILABLE MCP TOOLS, SPECIALIST AGENTS, and CURRENT REACT STATE & OBSERVATIONS.\n"
        "2. Understand Tool Specialization:\n"
        "   - search_bugs: Returns a list of matching bug candidates (id, title, component, status). It does NOT contain deep evidence like root cause, reproduction steps, or comments.\n"
        "   - get_bug: Retrieves full bug evidence (root cause, business impact, steps to reproduce, environment, versions, linked issues) for a specific bug_id.\n"
        "   - get_bug_history: Retrieves chronological lifecycle status transitions, reopen events, and discussion comments for a bug_id.\n"
        "   - get_related_bugs: Retrieves linked blocker/duplicate issues and related component bugs for a bug_id.\n"
        "   - get_bug_metrics, get_component_risk, get_bug_trends, get_release_risk, get_aging_bugs, get_reopened_bugs: Multi-bug aggregations.\n\n"
        "3. Iterative ReAct Workflow Rules:\n"
        "   - When investigating a specific bug by name/topic (e.g. 'Tell me about the Authentication Bug', 'Tell me about the Payments Bug'):\n"
        "     * Step 1: Call 'search_bugs' with 'query' to find the bug ID.\n"
        "     * Step 2: In the next iteration, inspect the search results. DO NOT finish immediately. Call 'get_bug' for the primary matching bug_id (e.g. 'BP-101') to retrieve full root cause, impact, and reproduction steps.\n"
        "     * Step 3 (Optional): If additional context is helpful (e.g. status changes, reopen cycles, comments, linked issues), call 'get_bug_history' or 'get_related_bugs'.\n"
        "     * Step 4: When sufficient evidence is collected, return action=FINISH.\n"
        "   - When answering comparative, ranking, or highest-risk bug questions (e.g. 'analyze authentication bugs and identify the highest-risk issue', 'compare payment bugs and find the most critical one', 'which open bug in billing has the highest risk?'):\n"
        "     * Step 1: ALWAYS call 'search_bugs' with 'query' (e.g. 'Authentication' or 'Payments') to discover all matching candidate issues. Do NOT call get_component_risk for comparing specific defects.\n"
        "     * Step 2..N: Call 'get_bug' for EACH candidate bug returned in search results (e.g. BP-101, BP-132, BP-133, BP-999) to retrieve full root cause, business impact, environment, and technical evidence.\n"
        "     * Comparison & Evaluation: Compare severity (Critical > High > Medium > Low), priority (High > Medium > Low), status (Open/Reopened > Resolved/Closed), business impact (e.g. total authentication lockout / security vulnerability vs cosmetic error), and environment (Production vs Staging). Do NOT select the first result arbitrarily without evaluating the candidates.\n"
        "     * Final Step: Once EVERY candidate bug has been evaluated with get_bug, return action=FINISH.\n"
        "   - When investigating a known bug ID (e.g. 'Tell me about BP-133'):\n"
        "     * Step 1: Call 'get_bug' with 'bug_id': 'BP-133'.\n"
        "     * Step 2 (Optional): Call 'get_bug_history' or 'get_related_bugs' if history or linked issues are useful.\n"
        "     * Step 3: Return action=FINISH.\n"
        "   - When answering component risk, component ranking, or hotspot questions (e.g. 'Which component has the highest risk?', 'Rank components by risk', 'What is the riskiest component?'):\n"
        "     * Call 'get_component_risk' (with 'arguments': {}).\n"
        "     * Do NOT call search_bugs unless specific bug tickets are explicitly requested.\n"
        "     * Identify the component with the maximum risk score, explain the contributing risk factors and open issue counts, and return action=FINISH.\n"
        "   - When answering aggregate or general list questions (e.g. 'Show me critical unresolved bugs', 'Show overall metrics'):\n"
        "     * Call the relevant tool ('search_bugs' with query/status, 'get_bug_metrics', 'get_bug_trends', etc.).\n"
        "     * Once observations are collected, return action=FINISH.\n"
        "   - Do NOT stop after search_bugs when deep investigation of a bug is requested. Always retrieve the bug details via get_bug.\n\n"
        "ALLOWED JSON ACTIONS:\n\n"
        "Action 1 — Call an MCP Tool:\n"
        "```json\n"
        "{\n"
        '  "action": "CALL_TOOL",\n'
        '  "tool": "<exact_tool_name_from_available_tools>",\n'
        '  "arguments": { "<required_arg_key>": "<arg_value>" }\n'
        "}\n"
        "```\n\n"
        "MCP TOOL ARGUMENT EXAMPLES:\n"
        '- When calling "search_bugs", provide search keyword in "query":\n'
        '  {"action": "CALL_TOOL", "tool": "search_bugs", "arguments": {"query": "Authentication"}}\n'
        '- When calling "get_bug", provide the bug ID in "bug_id":\n'
        '  {"action": "CALL_TOOL", "tool": "get_bug", "arguments": {"bug_id": "BP-101"}}\n'
        '- When calling "get_bug_history", provide "bug_id":\n'
        '  {"action": "CALL_TOOL", "tool": "get_bug_history", "arguments": {"bug_id": "BP-101"}}\n'
        '- When calling "get_related_bugs", provide "bug_id":\n'
        '  {"action": "CALL_TOOL", "tool": "get_related_bugs", "arguments": {"bug_id": "BP-101"}}\n'
        '- When calling aggregation tools (get_bug_metrics, get_component_risk, get_bug_trends, get_release_risk, get_aging_bugs, get_reopened_bugs):\n'
        '  {"action": "CALL_TOOL", "tool": "get_bug_metrics", "arguments": {}}\n\n'
        "Action 2 — Delegate to a Specialist Agent:\n"
        "```json\n"
        "{\n"
        '  "action": "DELEGATE",\n'
        '  "agent": "<Bug Analyst | Trend Analyst | Risk Analyst>",\n'
        '  "task": "<specific instruction for the specialist>",\n'
        '  "arguments": {}\n'
        "}\n"
        "```\n\n"
        "Action 3 — Finish (when sufficient observations are collected to answer the goal):\n"
        "```json\n"
        "{\n"
        '  "action": "FINISH"\n'
        "}\n"
        "```\n\n"
        "CRITICAL RULES:\n"
        "- Only choose tools from the provided AVAILABLE MCP TOOLS list.\n"
        "- Always provide required arguments.\n"
        "- Dynamically evaluate whether additional evidence is necessary based on the goal and observations.\n"
        "- Output ONLY a valid JSON object matching one of the three action schemas above. No conversational text outside the JSON."
    )




def build_react_user_prompt(
    goal: str,
    tools_text: str,
    available_agents: List[Dict[str, Any]],
    state_text: str,
) -> str:
    """Constructs the user content for a ReAct step."""
    try:
        agents_formatted = json.dumps(available_agents, ensure_ascii=False, indent=2)
    except Exception:
        agents_formatted = str(available_agents)

    return (
        f"USER GOAL:\n{goal}\n\n"
        f"AVAILABLE MCP TOOLS & SCHEMAS:\n```json\n{tools_text}\n```\n\n"
        f"AVAILABLE SPECIALIST AGENTS:\n```json\n{agents_formatted}\n```\n\n"
        f"CURRENT REACT STATE & OBSERVATIONS:\n```json\n{state_text}\n```\n\n"
        "Choose the single best NEXT action. Return ONLY valid JSON."
    )


def build_analysis_prompt(evidence_text: str, question: str) -> str:
    """Builds the prompt for evidence-grounded final bug analysis report."""
    return (
        "You are an expert software reliability engineer analyzing bug intelligence evidence.\n\n"
        f"EVIDENCE (GROUND TRUTH):\n```json\n{evidence_text}\n```\n\n"
        f"USER QUESTION:\n{question}\n\n"
        "INSTRUCTIONS:\n"
        "Produce an evidence-grounded technical analysis following this structure:\n"
        "1. Executive Summary (if comparative, explicitly name and highlight the highest-risk issue)\n"
        "2. Bug Details / Evaluation Matrix (if multiple bugs evaluated, present a comparative table of Bug ID, Title, Severity, Priority, Status, Environment, Business Impact, Risk Level)\n"
        "3. Problem Analysis (facts vs AI hypotheses clearly distinguished; compare root causes and blast radii across candidates)\n"
        "4. Impact & Risk Assessment (compare severity, production impact, security exposure, and regression risks)\n"
        "5. Highest-Risk Issue Determination & Rationale (if comparative, justify why the selected issue is the top risk compared to others)\n"
        "6. Recommended Actions & Mitigation Priority\n\n"
        "CRITICAL GROUNDING RULES:\n"
        "- Only state facts directly supported by the evidence.\n"
        "- If root cause or impact cannot be confirmed from the evidence, explicitly state that evidence is insufficient.\n"
        "- Do not invent bug IDs, numbers, metrics, or logs not present in the evidence.\n"
        "- Return clean, professional Markdown."
    )
