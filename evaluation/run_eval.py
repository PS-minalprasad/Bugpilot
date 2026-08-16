"""
BugPilot — Evaluation & Load Test CLI Runner
============================================
Runs the complete multi-agent evaluation suite and load test,
computes groundedness, intent accuracy, latency percentiles, and throughput,
and generates evaluation_report.json and a terminal summary.
"""

import asyncio
import json
import os
import sys
from datetime import datetime

from evaluation.evaluator import BugPilotEvaluator
from evaluation.load_tester import BugPilotLoadTester
from backend.database.repository import init_db, db_create_issue, db_get_issue_by_id_or_key


def ensure_seed_data():
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


async def main():
    print("=" * 80)
    print("  BUGPILOT MULTI-AGENT & MCP EVALUATION FRAMEWORK")
    print("=" * 80)
    print("Initializing test environment & isolated data fixtures...")
    ensure_seed_data()

    # 1. Run Agent & MCP Evaluation Suite
    print("\n[1/2] Executing Golden Evaluation Dataset (20 representative queries)...")
    evaluator = BugPilotEvaluator()
    eval_summary = await evaluator.run_evaluation()

    print(f"  [OK] Processed {eval_summary.total_queries} queries.")
    print(f"  [OK] Task Success Rate: {eval_summary.task_success_rate * 100:.1f}% ({eval_summary.passed_queries}/{eval_summary.total_queries})")
    print(f"  [OK] Intent Accuracy: {eval_summary.intent_accuracy * 100:.1f}%")
    print(f"  [OK] Agent Routing Accuracy: {eval_summary.agent_routing_accuracy * 100:.1f}%")
    print(f"  [OK] MCP Tool Selection Accuracy: {eval_summary.mcp_tool_accuracy * 100:.1f}%")
    print(f"  [OK] Groundedness: {eval_summary.groundedness_rate * 100:.1f}%")
    print(f"  [OK] Hallucination Rate: {eval_summary.hallucination_rate * 100:.1f}%")
    print(f"  [OK] Tool Call Success Rate: {eval_summary.tool_call_success_rate * 100:.1f}%")
    print(f"  [OK] Tool Usage Efficiency: {eval_summary.tool_usage_efficiency * 100:.1f}%")
    print(f"  [OK] Average Reflection Score: {eval_summary.average_reflection_score:.2f} / 1.00")
    print(f"  [OK] Latency: Mean={eval_summary.latency.mean}s, P50={eval_summary.latency.p50}s, P95={eval_summary.latency.p95}s, P99={eval_summary.latency.p99}s")

    # 2. Run Scalability & Concurrency Load Test
    print("\n[2/2] Executing Scalability Load Test (1, 5, 10, 25, 50 concurrent users)...")
    load_tester = BugPilotLoadTester()
    load_report = await load_tester.run_load_test(concurrency_levels=[1, 5, 10, 25, 50], requests_per_user=2)

    for c_res in load_report.concurrency_results:
        print(f"  * Concurrency {c_res.concurrency:2d} users: {c_res.throughput_rps:6.2f} req/s | P50={c_res.p50_latency_seconds:.4f}s | P95={c_res.p95_latency_seconds:.4f}s | Error Rate={c_res.error_rate * 100:.1f}%")

    # 3. Export Comprehensive JSON Evaluation Report
    full_report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "system": "BugPilot Multi-Agent Engineering Intelligence Platform",
        "agent_evaluation": eval_summary.model_dump(),
        "load_test_evaluation": load_report.model_dump(),
    }

    report_path = os.path.join(os.getcwd(), "evaluation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)

    print(f"\n[OK] Evaluation report successfully saved to: {report_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
