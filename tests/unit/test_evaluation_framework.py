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
    """1. Verify golden dataset contains 20 valid samples with unique query IDs."""
    assert len(GOLDEN_EVALUATION_DATASET) >= 20
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
        ]
        assert len(sample.expected_agents) > 0
        assert len(sample.expected_tools) > 0


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
