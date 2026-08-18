"""
BugPilot — Evaluation Framework Unit Tests
==========================================
Tests the evaluation metrics engine, golden dataset schema,
grounding validation, latency percentiles, and load tester harness.
"""

import pytest
import os
import json

from evaluation.golden_dataset import GOLDEN_EVALUATION_DATASET, EvaluationSample
from evaluation.evaluator import BugPilotEvaluator, LatencyStats
from evaluation.load_tester import BugPilotLoadTester
from mcp_client.client import MCPClient
from backend.database.repository import init_db, db_create_issue, db_get_issue_by_id_or_key


@pytest.fixture(autouse=True)
def setup_eval_env():
    init_db()
    iss = db_get_issue_by_id_or_key("iss-auth-99", org_id="org-acme")
    if not iss:
        db_create_issue(
            org_id="org-acme",
            data={
                "id": "iss-auth-99",
                "issue_key": "BP-999",
                "title": "Authentication token validation error",
                "description": "Token exchange fails on boundary expiration.",
                "status": "Open",
                "priority": "High",
                "severity": "Critical",
                "project": "BugPilot",
                "component": "Authentication",
                "assignee": "Auth Dev",
                "reporter": "Auth Reporter",
            },
        )


def test_1_golden_dataset_schema():
    """1. Verify golden dataset contains at least 23 valid samples with unique query IDs."""
    assert len(GOLDEN_EVALUATION_DATASET) >= 23
    query_ids = [s.query_id for s in GOLDEN_EVALUATION_DATASET]
    assert len(query_ids) == len(set(query_ids)), "Duplicate query IDs in dataset."

    for sample in GOLDEN_EVALUATION_DATASET:
        assert sample.query_id.startswith("eval-")
        assert len(sample.query) > 5
        assert sample.expected_intent in [
            "SPECIFIC_BUG",
            "BUG_SEARCH",
            "METRIC",
            "METRICS",
            "TREND",
            "RISK",
            "COMPONENT_ANALYSIS",
            "RELEASE_RISK",
            "AGING_BUGS",
            "REOPENED_BUGS",
            "GENERAL_REPORT",
            "COMPARATIVE_RISK",
            "OUT_OF_DOMAIN",
        ]
        assert len(sample.expected_agents) > 0


def test_2_latency_stats_percentiles():
    """2. Test percentile calculations for LatencyStats."""
    latencies = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    stats = BugPilotEvaluator._compute_percentiles(latencies)

    assert stats.mean == 0.055
    assert stats.p50 == 0.05
    assert stats.max == 0.10
    assert stats.p95 > stats.p50


@pytest.mark.asyncio
async def test_3_evaluator_single_sample_execution():
    """3. Test evaluating a single sample from the golden dataset."""
    sample = GOLDEN_EVALUATION_DATASET[0]  # BP-999 lookup
    evaluator = BugPilotEvaluator()

    async with MCPClient() as client:
        res = await evaluator.evaluate_sample(sample, client)

        assert res.query_id == sample.query_id
        assert res.intent_correct is True
        assert res.agent_routing_correct is True
        assert res.tool_selection_correct is True
        assert res.task_success is True
        assert res.hallucination_detected is False
        assert res.groundedness_score >= 0.80
        assert res.reflection_verdict in ["CONFIRM", "CORRECT"]
        assert res.reflection_quality_score > 0.0
        assert res.trajectory_valid is True
        assert res.instruction_followed is True
        assert res.safety_passed is True
        assert res.estimated_tokens > 0
        assert res.latency_seconds > 0.0


@pytest.mark.asyncio
async def test_4_load_tester_concurrency_execution():
    """4. Test load tester on concurrency level 2."""
    load_tester = BugPilotLoadTester(queries=["What is the status of BP-999?", "How many bugs are open?"])
    c_res = await load_tester.test_concurrency_level(concurrency=2, requests_per_user=1)

    assert c_res.concurrency == 2
    assert c_res.total_requests == 2
    assert c_res.successful_requests == 2
    assert c_res.error_rate == 0.0
    assert c_res.throughput_rps > 0.0
    assert c_res.p50_latency_seconds > 0.0


@pytest.mark.asyncio
async def test_5_evaluator_11_evaluation_dimensions():
    """5. Test full EvaluationSummary aggregates across all 11 required dimensions."""
    sample_subset = [GOLDEN_EVALUATION_DATASET[0], GOLDEN_EVALUATION_DATASET[5]]
    evaluator = BugPilotEvaluator(dataset=sample_subset)

    summary = await evaluator.run_evaluation()

    # 1. Task/Goal Success
    assert summary.task_success_rate >= 0.90
    assert summary.total_queries == 2
    assert summary.passed_queries == 2

    # 2. Tool Selection & Tool Call Success
    assert summary.mcp_tool_accuracy >= 0.90
    assert summary.tool_call_success_rate == 1.0

    # 3. Tool Usage Efficiency
    assert summary.tool_usage_efficiency > 0.0

    # 4. Decision/Reasoning Quality
    assert summary.decision_reasoning_quality >= 0.85
    assert summary.average_reflection_score >= 0.85

    # 5. Planning/Trajectory Accuracy
    assert summary.trajectory_accuracy == 1.0
    assert summary.agent_routing_accuracy >= 0.90

    # 6. Groundedness / Hallucination
    assert summary.groundedness_rate >= 0.80
    assert summary.hallucination_rate == 0.0

    # 7. Reliability & Recovery
    assert summary.recovery_rate == 1.0

    # 8. Latency
    assert summary.latency.mean > 0.0
    assert summary.latency.p50 > 0.0

    # 9. Token / Cost Usage
    assert summary.average_tokens_per_query > 0
    assert summary.estimated_total_cost_usd >= 0.0

    # 10. Instruction Following
    assert summary.instruction_following_rate == 1.0

    # 11. Safety / Robustness
    assert summary.safety_robustness_score == 1.0


@pytest.mark.asyncio
async def test_6_recent_project_samples_evaluation():
    """6. Test evaluation on out-of-domain guardrail and component risk samples."""
    evaluator = BugPilotEvaluator()

    # eval-21: Out of domain
    sample_ood = next(s for s in GOLDEN_EVALUATION_DATASET if s.query_id == "eval-21-out-of-domain-guardrail")
    # eval-23: Component risk
    sample_comp = next(s for s in GOLDEN_EVALUATION_DATASET if s.query_id == "eval-23-component-highest-risk")

    async with MCPClient() as client:
        res_ood = await evaluator.evaluate_sample(sample_ood, client)
        assert res_ood.intent_correct is True
        assert res_ood.tool_selection_correct is True
        assert res_ood.task_success is True
        assert res_ood.safety_passed is True
        assert "I can only help with BugPilot" in res_ood.final_answer_snippet

        res_comp = await evaluator.evaluate_sample(sample_comp, client)
        assert res_comp.intent_correct is True
        assert res_comp.tool_selection_correct is True
        assert res_comp.task_success is True
        assert "Authentication" in res_comp.final_answer

