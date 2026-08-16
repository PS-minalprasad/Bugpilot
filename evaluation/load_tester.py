"""
BugPilot — Scalability & Load Testing Runner
============================================
Evaluates performance under concurrent user loads:
1, 5, 10, 25, 50 concurrent simulated users.
Measures:
- Throughput (Requests / Second)
- P50, P95, P99 Latency
- Error Rate
Uses deterministic/in-memory provider paths without modifying production data.
"""

import asyncio
import time
import math
from typing import List, Dict, Any
from pydantic import BaseModel

from mcp_client.client import MCPClient
from agents.orchestrator import OrchestratorAgent


class ConcurrencyLevelResult(BaseModel):
    concurrency: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float
    duration_seconds: float
    throughput_rps: float
    p50_latency_seconds: float
    p95_latency_seconds: float
    p99_latency_seconds: float
    max_latency_seconds: float


class LoadTestReport(BaseModel):
    test_queries: List[str]
    concurrency_results: List[ConcurrencyLevelResult]


class BugPilotLoadTester:
    """
    Simulates concurrent user load against BugPilot multi-agent MCP orchestration.
    """

    DEFAULT_TEST_QUERIES = [
        "What is the status of BP-999?",
        "How many bugs are open?",
        "What is the current bug trend?",
        "Which component has the highest risk?",
        "Search for all open billing bugs",
    ]

    def __init__(self, queries: List[str] = None) -> None:
        self.queries = queries or self.DEFAULT_TEST_QUERIES

    async def _worker_task(
        self,
        query: str,
        client: MCPClient,
    ) -> Dict[str, Any]:
        orchestrator = OrchestratorAgent(mcp_client=client)
        start = time.perf_counter()
        try:
            res = await orchestrator.run(query)
            elapsed = time.perf_counter() - start
            return {"success": res.error is None, "latency": elapsed}
        except Exception:
            elapsed = time.perf_counter() - start
            return {"success": False, "latency": elapsed}

    async def test_concurrency_level(
        self,
        concurrency: int,
        requests_per_user: int = 2,
    ) -> ConcurrencyLevelResult:
        total_requests = concurrency * requests_per_user
        latencies: List[float] = []
        successful = 0
        failed = 0

        async with MCPClient() as client:
            tasks = []
            for i in range(total_requests):
                query = self.queries[i % len(self.queries)]
                tasks.append(self._worker_task(query, client))

            start_all = time.perf_counter()
            # Execute tasks with bounded concurrency
            semaphore = asyncio.Semaphore(concurrency)

            async def sem_task(t):
                async with semaphore:
                    return await t

            results = await asyncio.gather(*(sem_task(t) for t in tasks))
            total_duration = time.perf_counter() - start_all

        for r in results:
            latencies.append(r["latency"])
            if r["success"]:
                successful += 1
            else:
                failed += 1

        sorted_vals = sorted(latencies) if latencies else [0.0]
        n = len(sorted_vals)

        def pct(p: float) -> float:
            idx = int(math.ceil(p * n)) - 1
            return sorted_vals[max(0, min(idx, n - 1))]

        throughput = round(total_requests / total_duration, 2) if total_duration > 0 else 0.0
        error_rate = round(failed / total_requests, 4) if total_requests > 0 else 0.0

        return ConcurrencyLevelResult(
            concurrency=concurrency,
            total_requests=total_requests,
            successful_requests=successful,
            failed_requests=failed,
            error_rate=error_rate,
            duration_seconds=round(total_duration, 3),
            throughput_rps=throughput,
            p50_latency_seconds=round(float(pct(0.50)), 4),
            p95_latency_seconds=round(float(pct(0.95)), 4),
            p99_latency_seconds=round(float(pct(0.99)), 4),
            max_latency_seconds=round(float(sorted_vals[-1]), 4),
        )

    async def run_load_test(
        self,
        concurrency_levels: List[int] = [1, 5, 10, 25, 50],
        requests_per_user: int = 2,
    ) -> LoadTestReport:
        concurrency_results: List[ConcurrencyLevelResult] = []
        for c in concurrency_levels:
            res = await self.test_concurrency_level(c, requests_per_user=requests_per_user)
            concurrency_results.append(res)

        return LoadTestReport(
            test_queries=self.queries,
            concurrency_results=concurrency_results,
        )
