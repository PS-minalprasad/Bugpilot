"""
BugPilot — Golden Evaluation Dataset
====================================
Defines representative user queries with ground-truth expectations for:
- Intent
- Expected Agent(s)
- Expected MCP Tool(s)
- Required Facts (must be in response)
- Forbidden Claims (unsupported hallucinations)
- Category / Difficulty
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class EvaluationSample(BaseModel):
    query_id: str
    query: str
    expected_intent: str
    expected_agents: List[str]
    expected_tools: List[str]
    required_facts: List[str] = Field(default_factory=list)
    forbidden_claims: List[str] = Field(default_factory=list)
    category: str = "general"
    description: str = ""
    is_failure_scenario: bool = False
    is_crud_scenario: bool = False


GOLDEN_EVALUATION_DATASET: List[EvaluationSample] = [
    # 1. SPECIFIC_BUG QUERIES
    EvaluationSample(
        query_id="eval-01-specific-bug-key",
        query="What is the status of BP-999?",
        expected_intent="SPECIFIC_BUG",
        expected_agents=["Bug Analyst"],
        expected_tools=["search_bugs", "get_bug"],
        required_facts=["BP-999", "Authentication", "Open", "Critical", "High"],
        forbidden_claims=["JWT key was leaked", "Database corrupted", "Fixed in v1.2"],
        category="specific_bug",
        description="Lookup bug by exact issue key BP-999"
    ),
    EvaluationSample(
        query_id="eval-02-specific-bug-component",
        query="Tell me about the Authentication bug",
        expected_intent="SPECIFIC_BUG",
        expected_agents=["Bug Analyst"],
        expected_tools=["search_bugs", "get_bug"],
        required_facts=["Authentication", "BP-999"],
        forbidden_claims=["Root cause confirmed as buffer overflow"],
        category="specific_bug",
        description="Lookup bug by component name"
    ),
    EvaluationSample(
        query_id="eval-03-specific-bug-title",
        query="Show details for token validation error",
        expected_intent="SPECIFIC_BUG",
        expected_agents=["Bug Analyst"],
        expected_tools=["search_bugs", "get_bug"],
        required_facts=["token", "validation"],
        forbidden_claims=["5000 users affected"],
        category="specific_bug",
        description="Lookup bug by title fragment"
    ),

    # 2. BUG_SEARCH QUERIES
    EvaluationSample(
        query_id="eval-04-bug-search-open",
        query="Search for all open billing bugs",
        expected_intent="BUG_SEARCH",
        expected_agents=["Bug Analyst"],
        expected_tools=["search_bugs"],
        required_facts=["Billing"],
        forbidden_claims=["All billing bugs were deleted"],
        category="search",
        description="Search bugs filtered by component and status"
    ),
    EvaluationSample(
        query_id="eval-05-bug-search-critical",
        query="Find critical severity bugs in the project",
        expected_intent="BUG_SEARCH",
        expected_agents=["Bug Analyst"],
        expected_tools=["search_bugs"],
        required_facts=["Critical"],
        forbidden_claims=["Zero bugs in project"],
        category="search",
        description="Search bugs filtered by critical severity"
    ),

    # 3. METRICS QUERIES
    EvaluationSample(
        query_id="eval-06-metrics-summary",
        query="How many total bugs do we have?",
        expected_intent="METRIC",
        expected_agents=["Bug Analyst"],
        expected_tools=["get_bug_metrics"],
        required_facts=["total bugs"],
        forbidden_claims=["10000 bugs"],
        category="metrics",
        description="General bug count and summary metrics"
    ),
    EvaluationSample(
        query_id="eval-07-metrics-open-bugs",
        query="How many bugs are currently open?",
        expected_intent="METRIC",
        expected_agents=["Bug Analyst"],
        expected_tools=["get_bug_metrics"],
        required_facts=["open"],
        forbidden_claims=["Zero open bugs"],
        category="metrics",
        description="Open bugs count"
    ),
    EvaluationSample(
        query_id="eval-08-metrics-breakdown",
        query="Show me bug counts by component and severity",
        expected_intent="METRIC",
        expected_agents=["Bug Analyst"],
        expected_tools=["get_bug_metrics"],
        required_facts=["component", "severity"],
        forbidden_claims=["AI component failed"],
        category="metrics",
        description="Component and severity distribution"
    ),

    # 4. TREND QUERIES
    EvaluationSample(
        query_id="eval-09-trends-general",
        query="What is the current bug trend?",
        expected_intent="TREND",
        expected_agents=["Trend Analyst", "Bug Analyst"],
        expected_tools=["get_bug_trends"],
        required_facts=["trend"],
        forbidden_claims=["Bugs decreased by 99% yesterday"],
        category="trends",
        description="Time-series bug volume and resolution trends"
    ),
    EvaluationSample(
        query_id="eval-10-trends-component",
        query="Are Authentication bugs increasing this sprint?",
        expected_intent="TREND",
        expected_agents=["Trend Analyst", "Bug Analyst"],
        expected_tools=["get_bug_trends"],
        required_facts=["trend", "Authentication"],
        forbidden_claims=["Authentication team resigned"],
        category="trends",
        description="Component-specific historical trend inquiry"
    ),

    # 5. RISK & COMPONENT ANALYSIS
    EvaluationSample(
        query_id="eval-11-risk-highest-component",
        query="Which component has the highest risk?",
        expected_intent="RISK",
        expected_agents=["Risk Analyst", "Bug Analyst"],
        expected_tools=["get_component_risk"],
        required_facts=["risk"],
        forbidden_claims=["Risk score is 1000 out of 10"],
        category="risk",
        description="Component risk analysis"
    ),
    EvaluationSample(
        query_id="eval-12-risk-specific-component",
        query="Analyze component risk for Authentication",
        expected_intent="RISK",
        expected_agents=["Risk Analyst", "Bug Analyst"],
        expected_tools=["get_component_risk"],
        required_facts=["Authentication", "Risk"],
        forbidden_claims=["Production is down"],
        category="risk",
        description="Detailed component risk assessment"
    ),

    # 6. RELEASE RISK
    EvaluationSample(
        query_id="eval-13-release-risk-safety",
        query="Is the upcoming release safe?",
        expected_intent="RELEASE_RISK",
        expected_agents=["Risk Analyst", "Bug Analyst"],
        expected_tools=["get_release_risk", "get_bug_metrics", "get_component_risk"],
        required_facts=["release", "risk"],
        forbidden_claims=["Release was cancelled by CEO"],
        category="release_risk",
        description="Release safety evaluation"
    ),

    # 7. AGING & REOPENED BUGS
    EvaluationSample(
        query_id="eval-14-aging-bugs",
        query="Show me old unresolved aging bugs",
        expected_intent="AGING_BUGS",
        expected_agents=["Risk Analyst", "Bug Analyst"],
        expected_tools=["get_aging_bugs"],
        required_facts=["aging"],
        forbidden_claims=["All bugs are 10 years old"],
        category="aging",
        description="Aging bug identification"
    ),
    EvaluationSample(
        query_id="eval-15-reopened-bugs",
        query="Which bugs have been reopened multiple times?",
        expected_intent="REOPENED_BUGS",
        expected_agents=["Trend Analyst", "Bug Analyst"],
        expected_tools=["get_reopened_bugs"],
        required_facts=["reopen"],
        forbidden_claims=["Every bug reopened 50 times"],
        category="reopened",
        description="Reopened bug tracking"
    ),

    # 8. GENERAL ENGINEERING HEALTH REPORT
    EvaluationSample(
        query_id="eval-16-general-health-report",
        query="Give me a complete engineering health report",
        expected_intent="GENERAL_REPORT",
        expected_agents=["Bug Analyst", "Risk Analyst", "Trend Analyst"],
        expected_tools=["get_bug_metrics", "get_bug_trends", "get_component_risk"],
        required_facts=["Executive Summary", "total bugs"],
        forbidden_claims=["BugPilot server melted"],
        category="report",
        description="Multi-agent executive engineering report"
    ),

    # 9. MISSING BUG & EDGE CASES
    EvaluationSample(
        query_id="eval-17-nonexistent-bug",
        query="Tell me about bug NONEXISTENT-99999",
        expected_intent="SPECIFIC_BUG",
        expected_agents=["Bug Analyst"],
        expected_tools=["search_bugs", "get_bug"],
        required_facts=["couldn't find", "no bug found"],
        forbidden_claims=["NONEXISTENT-99999 is Critical and Open"],
        category="missing_bug",
        description="Graceful handling of missing bug request"
    ),
    EvaluationSample(
        query_id="eval-18-missing-root-cause",
        query="What is the exact confirmed root cause of BP-999?",
        expected_intent="SPECIFIC_BUG",
        expected_agents=["Bug Analyst"],
        expected_tools=["search_bugs", "get_bug"],
        required_facts=["does not provide enough evidence", "root cause"],
        forbidden_claims=["The confirmed root cause is a race condition in Redis"],
        category="grounding",
        description="Disclaims unverified root cause when evidence is absent"
    ),
    EvaluationSample(
        query_id="eval-19-missing-historical-data",
        query="What was the bug count 3 years ago?",
        expected_intent="TREND",
        expected_agents=["Trend Analyst", "Bug Analyst"],
        expected_tools=["get_bug_trends"],
        required_facts=["Historical data", "not retrieved", "trend", "data"],
        forbidden_claims=["3 years ago we had exactly 421 bugs"],
        category="grounding",
        description="Refrains from fabricating historical metrics"
    ),

    # 10. MULTI-GOAL COMPLEX QUERIES
    EvaluationSample(
        query_id="eval-20-complex-multi-goal",
        query="Analyze Authentication bugs and tell me whether they are becoming a release risk.",
        expected_intent="RISK",
        expected_agents=["Bug Analyst", "Risk Analyst", "Trend Analyst"],
        expected_tools=["get_component_risk", "get_bug_trends", "search_bugs"],
        required_facts=["Authentication", "risk"],
        forbidden_claims=["Entire system is completely halted"],
        category="complex",
        description="Multi-agent composite query combining search, trend, and risk"
    ),
]
