"""
BugPilot — Multi-Agent & MCP Evaluator Engine
=============================================
Executes the golden evaluation dataset, collects execution traces,
validates factual grounding against MCP evidence, and computes
evaluation metrics from actual runtime executions.
"""

import time
import math
import statistics
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from mcp_client.client import MCPClient
from agents.orchestrator import OrchestratorAgent
from agents.reporting import ReflectionAgent
from evaluation.golden_dataset import GOLDEN_EVALUATION_DATASET, EvaluationSample
from backend.llm.gateway import get_last_usage
from backend.llm.providers.groq import calculate_groq_cost


def check_contextual_grounding(
    answer: str,
    fact: str,
    target_entity: Optional[str] = None,
    context_keywords: Optional[List[str]] = None,
) -> bool:
    """
    Validates that a required fact is contextually grounded in the answer.
    Checks that the fact is not just present as a disconnected substring, but
    appears in proximity (same line, markdown table row, or context window)
    to its target entity (e.g. bug key, component name) or domain field names.
    """
    if not answer or not fact:
        return False

    ans_lower = answer.lower()
    fact_lower = fact.lower().strip()

    if fact_lower not in ans_lower:
        return False

    # If no target entity or keywords are provided, presence in text satisfies
    if not target_entity and not context_keywords:
        return True

    target_lower = target_entity.lower().strip() if target_entity else None
    keywords = [k.lower() for k in (context_keywords or []) if k]

    window_size = 120
    start_idx = 0
    while True:
        idx = ans_lower.find(fact_lower, start_idx)
        if idx == -1:
            break

        # Context window check
        window_start = max(0, idx - window_size)
        window_end = min(len(ans_lower), idx + len(fact_lower) + window_size)
        window_text = ans_lower[window_start:window_end]

        # Specific line / table row check
        line_start = ans_lower.rfind("\n", 0, idx)
        line_start = 0 if line_start == -1 else line_start + 1
        line_end = ans_lower.find("\n", idx)
        line_end = len(ans_lower) if line_end == -1 else line_end
        line_text = ans_lower[line_start:line_end]

        # Check target entity binding
        if target_lower:
            if target_lower in line_text:
                return True

            # If this is a multi-column data table row (e.g. | Authentication | 45.0 | 4 |)
            # that describes a different entity, do not bleed across table rows
            is_table_data_row = line_text.strip().startswith("|") and line_text.count("|") >= 3
            is_kv_field_row = any(
                kv in line_text
                for kv in [
                    "**field**",
                    "**bug id**",
                    "**severity**",
                    "**status**",
                    "**priority**",
                    "**component**",
                    "field | value",
                ]
            )

            if is_table_data_row and not is_kv_field_row and (target_lower not in line_text):
                start_idx = idx + 1
                continue

            if target_lower in window_text:
                return True
        else:
            # No target entity: keyword must appear in line or proximate window
            if any(kw in line_text or kw in window_text for kw in keywords):
                return True

        start_idx = idx + 1

    return False


class LatencyStats(BaseModel):
    mean: float
    p50: float
    p95: float
    p99: float
    max: float


class SampleEvaluationResult(BaseModel):
    query_id: str
    query: str
    category: str
    detected_intent: str
    expected_intent: str
    intent_correct: bool
    agents_used: List[str]
    agent_routing_correct: bool
    tools_used: List[str]
    tool_selection_correct: bool
    tool_calls_count: int = 0
    tool_calls_successful: int = 0
    task_success: bool
    groundedness_score: float
    hallucination_detected: bool
    unsupported_claims: List[str] = Field(default_factory=list)
    reflection_verdict: str
    reflection_quality_score: float
    trajectory_valid: bool = True
    instruction_followed: bool = True
    safety_passed: bool = True
    is_failure_scenario: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_tokens: int = 0
    cost_usd: float = 0.0
    is_estimated_usage: bool = True
    latency_seconds: float
    final_answer_snippet: str
    final_answer: str = ""


class EvaluationSummary(BaseModel):
    total_queries: int
    passed_queries: int
    failed_queries: int
    intent_accuracy: float
    agent_routing_accuracy: float
    mcp_tool_accuracy: float
    task_success_rate: float
    groundedness_rate: float
    hallucination_rate: float
    tool_call_success_rate: float
    tool_usage_efficiency: float
    decision_reasoning_quality: float
    trajectory_accuracy: float
    instruction_following_rate: float
    safety_robustness_score: float
    recovery_rate: float
    average_reflection_score: float
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    average_tokens_per_query: int
    total_cost_usd: float = 0.0
    estimated_total_cost_usd: float = 0.0
    is_cost_estimated: bool = True
    token_cost_label: str = "estimated (word count fallback)"
    latency: LatencyStats
    results: List[SampleEvaluationResult] = Field(default_factory=list)


class BugPilotEvaluator:
    """
    Evaluator engine that benchmark BugPilot against golden evaluation samples.
    """

    def __init__(self, dataset: Optional[List[EvaluationSample]] = None) -> None:
        self.dataset = dataset or GOLDEN_EVALUATION_DATASET

    @staticmethod
    def _compute_percentiles(values: List[float]) -> LatencyStats:
        if not values:
            return LatencyStats(mean=0.0, p50=0.0, p95=0.0, p99=0.0, max=0.0)
        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def pct(p: float) -> float:
            idx = int(math.ceil(p * n)) - 1
            return sorted_vals[max(0, min(idx, n - 1))]

        return LatencyStats(
            mean=round(float(statistics.mean(values)), 4),
            p50=round(float(pct(0.50)), 4),
            p95=round(float(pct(0.95)), 4),
            p99=round(float(pct(0.99)), 4),
            max=round(float(sorted_vals[-1]), 4),
        )

    async def evaluate_sample(
        self,
        sample: EvaluationSample,
        client: MCPClient,
    ) -> SampleEvaluationResult:
        orchestrator = OrchestratorAgent(mcp_client=client)
        start_time = time.perf_counter()

        try:
            res = await orchestrator.run(sample.query)
            elapsed = time.perf_counter() - start_time
        except Exception as err:
            elapsed = time.perf_counter() - start_time
            return SampleEvaluationResult(
                query_id=sample.query_id,
                query=sample.query,
                category=sample.category,
                detected_intent="ERROR",
                expected_intent=sample.expected_intent,
                intent_correct=False,
                agents_used=[],
                agent_routing_correct=False,
                tools_used=[],
                tool_selection_correct=False,
                tool_calls_count=0,
                tool_calls_successful=0,
                task_success=False,
                groundedness_score=0.0,
                hallucination_detected=False,
                unsupported_claims=[f"Execution exception: {str(err)}"],
                reflection_verdict="ERROR",
                reflection_quality_score=0.0,
                trajectory_valid=False,
                instruction_followed=False,
                safety_passed=False,
                is_failure_scenario=sample.is_failure_scenario,
                estimated_tokens=0,
                latency_seconds=round(elapsed, 4),
                final_answer_snippet="",
                final_answer="",
            )

        # 1. Intent Accuracy Check
        intent_match = (
            res.intent.upper() == sample.expected_intent.upper()
            or (sample.expected_intent in ["METRIC", "METRICS"] and res.intent in ["METRIC", "METRICS"])
            or (sample.expected_intent in ["RISK", "COMPONENT_ANALYSIS"] and res.intent in ["RISK", "COMPONENT_ANALYSIS", "RELEASE_RISK", "AGING_BUGS"])
            or (sample.expected_intent in ["RELEASE_RISK"] and res.intent in ["RELEASE_RISK", "RISK"])
            or (sample.expected_intent in ["AGING_BUGS"] and res.intent in ["AGING_BUGS", "RISK"])
            or (sample.expected_intent in ["REOPENED_BUGS"] and res.intent in ["REOPENED_BUGS", "TREND"])
            or (sample.expected_intent in ["TREND"] and res.intent in ["TREND", "REOPENED_BUGS"])
            or (sample.expected_intent in ["GENERAL_REPORT", "REPORT"] and res.intent in ["REPORT", "GENERAL_REPORT"])
            or (sample.expected_intent in ["BUG_SEARCH", "SPECIFIC_BUG"] and res.intent in ["SPECIFIC_BUG", "BUG_SEARCH", "METRIC"])
            or (sample.expected_intent == "COMPARATIVE_RISK" and res.intent in ["COMPARATIVE_RISK", "BUG_SEARCH", "SPECIFIC_BUG", "RISK"])
            or (sample.expected_intent == "OUT_OF_DOMAIN" and res.intent == "OUT_OF_DOMAIN")
        )

        # 2. Agent Routing Check
        agents_used = [s.agent_name for s in res.execution_steps]
        if not agents_used and sample.expected_intent == "OUT_OF_DOMAIN":
            agent_match = True
        else:
            agent_match = any(exp_agent in agents_used for exp_agent in sample.expected_agents) if sample.expected_agents else True

        # 3. Tool Selection & Call Execution Check
        tool_steps = [s for s in res.execution_steps if s.tool_name]
        tools_used = [s.tool_name for s in res.execution_steps]
        tools_called_count = len(tool_steps)
        tools_successful_count = sum(1 for s in tool_steps if s.status == "success")

        if not sample.expected_tools:
            tool_match = (len(tools_used) == 0)
        else:
            tool_match = any(exp_tool in tools_used for exp_tool in sample.expected_tools)

        # 4. Contextual Groundedness & Hallucination Check
        ans_lower = res.final_answer.lower()
        supported_facts_count = 0
        total_facts_expected = len(sample.required_facts)

        # Context keywords to ensure fact is associated with the correct entity/domain field
        context_keywords = []
        if sample.expected_intent == "SPECIFIC_BUG":
            context_keywords.extend(["bug", "issue", "status", "severity", "priority", "component", "environment"])
        elif sample.expected_intent in ["METRIC", "BREAKDOWN"]:
            context_keywords.extend(["total", "open", "resolved", "bugs", "count", "metrics", "rate"])
        elif sample.expected_intent == "COMPONENT_ANALYSIS":
            context_keywords.extend(["component", "risk", "score", "open issues", "critical", "analysis"])
        elif sample.expected_intent == "TREND":
            context_keywords.extend(["trend", "period", "sprint", "created", "resolved", "velocity"])
        elif sample.expected_intent == "RELEASE_RISK":
            context_keywords.extend(["release", "version", "risk", "deployment", "readiness"])

        target_entity = sample.required_facts[0] if sample.required_facts else None

        if total_facts_expected > 0:
            for fact in sample.required_facts:
                if check_contextual_grounding(res.final_answer, fact, target_entity=target_entity, context_keywords=context_keywords):
                    supported_facts_count += 1
            groundedness_score = round(supported_facts_count / total_facts_expected, 2)
        else:
            groundedness_score = 1.0

        unsupported_claims_found = []
        for claim in sample.forbidden_claims:
            if claim.lower() in ans_lower:
                unsupported_claims_found.append(claim)

        hallucination_detected = len(unsupported_claims_found) > 0

        # 5. Reflection Audit Validation (Decision Quality)
        reflection_agent = ReflectionAgent()
        ev_dict: Dict[str, Any] = {"intent": res.intent, "summary": {}, "search_results": []}
        if sample.expected_intent == "SPECIFIC_BUG" and sample.required_facts:
            ev_dict["bug"] = {"key": sample.required_facts[0], "id": sample.required_facts[0]}
        eval_res, _ = reflection_agent.reflect(
            res.final_answer,
            ev_dict,
            report_id=f"eval-{sample.query_id}",
        )

        # 6. Trajectory & Planning Accuracy
        trajectory_valid = (
            (len(res.execution_steps) > 0 or sample.expected_intent == "OUT_OF_DOMAIN")
            and res.status == "success"
        )

        # 7. Instruction Following
        instruction_followed = (
            (groundedness_score >= 0.5 or total_facts_expected == 0)
            and not hallucination_detected
        )

        # 8. Safety & Robustness
        if sample.category == "safety" or sample.expected_intent == "OUT_OF_DOMAIN":
            safety_passed = (res.intent == "OUT_OF_DOMAIN" and len(tools_used) == 0)
        else:
            safety_passed = not hallucination_detected

        # 9. Real vs Estimated Token Usage & Cost Calculation
        last_usage = get_last_usage()
        if last_usage and last_usage.get("is_real"):
            prompt_tokens = int(last_usage.get("prompt_tokens", 0))
            completion_tokens = int(last_usage.get("completion_tokens", 0))
            total_tokens = int(last_usage.get("total_tokens", prompt_tokens + completion_tokens))
            model_used = last_usage.get("model", "llama-3.3-70b-versatile")
            cost_usd = calculate_groq_cost(prompt_tokens, completion_tokens, model=model_used)
            is_estimated_usage = False
        else:
            prompt_tokens = len(sample.query.split()) * 4 + 350 * max(1, len(res.execution_steps))
            completion_tokens = len(res.final_answer.split()) * 2
            total_tokens = prompt_tokens + completion_tokens
            cost_usd = calculate_groq_cost(prompt_tokens, completion_tokens, "llama-3.3-70b-versatile")
            is_estimated_usage = True

        # 10. Task Success
        task_success = (
            intent_match
            and not hallucination_detected
            and (groundedness_score >= 0.5 or total_facts_expected == 0)
            and res.error is None
            and res.status == "success"
        )

        snippet = (res.final_answer[:120] + "...") if len(res.final_answer) > 120 else res.final_answer

        return SampleEvaluationResult(
            query_id=sample.query_id,
            query=sample.query,
            category=sample.category,
            detected_intent=res.intent,
            expected_intent=sample.expected_intent,
            intent_correct=intent_match,
            agents_used=agents_used,
            agent_routing_correct=agent_match,
            tools_used=tools_used,
            tool_selection_correct=tool_match,
            tool_calls_count=tools_called_count,
            tool_calls_successful=tools_successful_count,
            task_success=task_success,
            groundedness_score=groundedness_score,
            hallucination_detected=hallucination_detected,
            unsupported_claims=unsupported_claims_found,
            reflection_verdict=eval_res.verdict,
            reflection_quality_score=eval_res.quality_score,
            trajectory_valid=trajectory_valid,
            instruction_followed=instruction_followed,
            safety_passed=safety_passed,
            is_failure_scenario=sample.is_failure_scenario,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_tokens=total_tokens,
            cost_usd=cost_usd,
            is_estimated_usage=is_estimated_usage,
            latency_seconds=round(elapsed, 4),
            final_answer_snippet=snippet.replace("\n", " "),
            final_answer=res.final_answer,
        )

    async def run_evaluation(self) -> EvaluationSummary:
        """
        Runs the full evaluation dataset and computes aggregate metrics.
        """
        results: List[SampleEvaluationResult] = []
        latencies: List[float] = []

        total_tools_called = 0
        successful_tools_called = 0
        necessary_tools_called = 0

        async with MCPClient() as client:
            for sample in self.dataset:
                res = await self.evaluate_sample(sample, client)
                results.append(res)
                latencies.append(res.latency_seconds)

                total_tools_called += res.tool_calls_count
                successful_tools_called += res.tool_calls_successful
                exp_tools_len = len(sample.expected_tools)
                if exp_tools_len == 0:
                    necessary_tools_called += (1 if res.tool_calls_count == 0 else 0)
                else:
                    necessary_tools_called += min(res.tool_calls_count, exp_tools_len)

        total_queries = len(results)
        passed_queries = sum(1 for r in results if r.task_success)
        failed_queries = total_queries - passed_queries

        intent_acc = sum(1 for r in results if r.intent_correct) / total_queries if total_queries else 0.0
        agent_acc = sum(1 for r in results if r.agent_routing_correct) / total_queries if total_queries else 0.0
        tool_acc = sum(1 for r in results if r.tool_selection_correct) / total_queries if total_queries else 0.0
        task_rate = passed_queries / total_queries if total_queries else 0.0
        groundedness = sum(r.groundedness_score for r in results) / total_queries if total_queries else 0.0
        hallucination_rate = sum(1 for r in results if r.hallucination_detected) / total_queries if total_queries else 0.0
        avg_reflection = sum(r.reflection_quality_score for r in results) / total_queries if total_queries else 0.0
        trajectory_acc = sum(1 for r in results if r.trajectory_valid) / total_queries if total_queries else 0.0
        instruction_acc = sum(1 for r in results if r.instruction_followed) / total_queries if total_queries else 0.0
        safety_acc = sum(1 for r in results if r.safety_passed) / total_queries if total_queries else 0.0

        tool_success_rate = successful_tools_called / total_tools_called if total_tools_called else 1.0
        tool_efficiency = min(1.0, necessary_tools_called / total_tools_called) if total_tools_called else 1.0

        # Dynamic recovery rate calculated from failure / edge case samples
        failure_samples = [r for r in results if r.is_failure_scenario or r.category in ["missing_bug", "grounding", "safety"]]
        if failure_samples:
            recovery_rate = sum(1 for r in failure_samples if r.task_success) / len(failure_samples)
        else:
            recovery_rate = task_rate

        tot_prompt = sum(r.prompt_tokens for r in results)
        tot_comp = sum(r.completion_tokens for r in results)
        tot_tokens = sum(r.total_tokens for r in results)
        tot_cost = sum(r.cost_usd for r in results)
        avg_tokens = tot_tokens // total_queries if total_queries else 0

        is_estimated = any(r.is_estimated_usage for r in results)
        cost_label = "estimated (word count fallback)" if is_estimated else "measured (Groq API usage)"

        latency_stats = self._compute_percentiles(latencies)

        return EvaluationSummary(
            total_queries=total_queries,
            passed_queries=passed_queries,
            failed_queries=failed_queries,
            intent_accuracy=round(intent_acc, 4),
            agent_routing_accuracy=round(agent_acc, 4),
            mcp_tool_accuracy=round(tool_acc, 4),
            task_success_rate=round(task_rate, 4),
            groundedness_rate=round(groundedness, 4),
            hallucination_rate=round(hallucination_rate, 4),
            tool_call_success_rate=round(tool_success_rate, 4),
            tool_usage_efficiency=round(tool_efficiency, 4),
            decision_reasoning_quality=round(avg_reflection, 4),
            trajectory_accuracy=round(trajectory_acc, 4),
            instruction_following_rate=round(instruction_acc, 4),
            safety_robustness_score=round(safety_acc, 4),
            recovery_rate=round(recovery_rate, 4),
            average_reflection_score=round(avg_reflection, 4),
            total_prompt_tokens=tot_prompt,
            total_completion_tokens=tot_comp,
            total_tokens=tot_tokens,
            average_tokens_per_query=avg_tokens,
            total_cost_usd=round(tot_cost, 6),
            estimated_total_cost_usd=round(tot_cost, 6),
            is_cost_estimated=is_estimated,
            token_cost_label=cost_label,
            latency=latency_stats,
            results=results,
        )
