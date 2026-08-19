"""
Lookup benchmark workload.

Measures:
  - Point lookup:   Fetch a single node by its indexed uid property
  - Indexed lookup:  Range scan on the uid index
"""

import logging
import random
from typing import List

from benchmark.metrics import Measurement, MetricsCollector
from benchmark.utils import time_operation
from config import BenchmarkConfig
from databases.base import GraphDatabaseAdapter

logger = logging.getLogger("benchmark.workloads.lookup")


def run_lookup_benchmark(
    adapter: GraphDatabaseAdapter,
    node_ids: List[int],
    config: BenchmarkConfig,
    collector: MetricsCollector,
) -> None:
    """
    Run lookup benchmarks:
      - point_lookup: fetch a single node by uid
      - indexed_lookup: range query on uid [min_id, min_id + 100]
    """
    rng = random.Random(config.random_seed)
    sample_ids = rng.sample(node_ids, min(config.benchmark_iterations, len(node_ids)))
    max_node = max(node_ids)

    # ── Point Lookup ─────────────────────────────────────────────────────
    logger.info(
        "[%s] Running point lookup (warmup=%d, iterations=%d) ...",
        adapter.name,
        config.warmup_iterations,
        config.benchmark_iterations,
    )

    # Warm-up
    for i in range(config.warmup_iterations):
        nid = sample_ids[i % len(sample_ids)]
        try:
            adapter.point_lookup(nid)
        except Exception as e:
            logger.warning("Warmup error (point_lookup %d): %s", nid, e)

    # Measurement
    for i in range(config.benchmark_iterations):
        nid = sample_ids[i % len(sample_ids)]
        try:
            elapsed_ms, _result = time_operation(adapter.point_lookup, nid)
            collector.record(
                Measurement(
                    database=adapter.name,
                    workload="lookup",
                    query="point_lookup",
                    iteration=i,
                    latency_ms=elapsed_ms,
                )
            )
        except Exception as e:
            collector.record(
                Measurement(
                    database=adapter.name,
                    workload="lookup",
                    query="point_lookup",
                    iteration=i,
                    latency_ms=0.0,
                    status="error",
                    error=str(e),
                )
            )

    logger.info("[%s] Point lookup complete.", adapter.name)

    # ── Indexed / Filtered Lookup ────────────────────────────────────────
    logger.info(
        "[%s] Running indexed lookup (warmup=%d, iterations=%d) ...",
        adapter.name,
        config.warmup_iterations,
        config.benchmark_iterations,
    )

    # Generate random range starts
    range_starts = [
        rng.randint(1, max(1, max_node - 100))
        for _ in range(config.benchmark_iterations)
    ]

    # Warm-up
    for i in range(config.warmup_iterations):
        start = range_starts[i % len(range_starts)]
        try:
            adapter.indexed_lookup(start, start + 100)
        except Exception as e:
            logger.warning("Warmup error (indexed_lookup): %s", e)

    # Measurement
    for i in range(config.benchmark_iterations):
        start = range_starts[i % len(range_starts)]
        try:
            elapsed_ms, _result = time_operation(
                adapter.indexed_lookup, start, start + 100
            )
            collector.record(
                Measurement(
                    database=adapter.name,
                    workload="lookup",
                    query="indexed_lookup",
                    iteration=i,
                    latency_ms=elapsed_ms,
                )
            )
        except Exception as e:
            collector.record(
                Measurement(
                    database=adapter.name,
                    workload="lookup",
                    query="indexed_lookup",
                    iteration=i,
                    latency_ms=0.0,
                    status="error",
                    error=str(e),
                )
            )

    logger.info("[%s] Indexed lookup complete.", adapter.name)
