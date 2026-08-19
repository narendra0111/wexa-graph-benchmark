"""
Traversal benchmark workload.

Measures 1-hop, 2-hop, and 3-hop traversal latencies using randomly
selected start nodes with a fixed seed for reproducibility.
"""

import logging
import random
from typing import List

from benchmark.metrics import Measurement, MetricsCollector
from benchmark.utils import time_operation
from config import BenchmarkConfig
from databases.base import GraphDatabaseAdapter

logger = logging.getLogger("benchmark.workloads.traversal")


def _select_start_nodes(
    node_ids: List[int], count: int, seed: int
) -> List[int]:
    """Select random start nodes with a fixed seed."""
    rng = random.Random(seed)
    return rng.sample(node_ids, min(count, len(node_ids)))


def run_traversal_benchmark(
    adapter: GraphDatabaseAdapter,
    node_ids: List[int],
    config: BenchmarkConfig,
    collector: MetricsCollector,
) -> None:
    """
    Run traversal benchmarks (1-hop, 2-hop, 3-hop).

    For each hop level:
      1. Warm up with config.warmup_iterations queries
      2. Measure config.benchmark_iterations queries
      3. Record latency for each iteration
    """
    start_nodes = _select_start_nodes(
        node_ids, config.traversal_sample_nodes, config.random_seed
    )

    for hop, method_name in [
        ("1hop", "traversal_1hop"),
        ("2hop", "traversal_2hop"),
        ("3hop", "traversal_3hop"),
    ]:
        method = getattr(adapter, method_name)
        logger.info(
            "[%s] Running %s traversal (warmup=%d, iterations=%d) ...",
            adapter.name,
            hop,
            config.warmup_iterations,
            config.benchmark_iterations,
        )

        # Warm-up
        for i in range(config.warmup_iterations):
            node = start_nodes[i % len(start_nodes)]
            try:
                method(node)
            except Exception as e:
                logger.warning("Warmup error (%s %s): %s", hop, node, e)

        # Measurement
        for i in range(config.benchmark_iterations):
            node = start_nodes[i % len(start_nodes)]
            try:
                elapsed_ms, _result = time_operation(method, node)
                collector.record(
                    Measurement(
                        database=adapter.name,
                        workload="traversal",
                        query=hop,
                        iteration=i,
                        latency_ms=elapsed_ms,
                    )
                )
            except Exception as e:
                collector.record(
                    Measurement(
                        database=adapter.name,
                        workload="traversal",
                        query=hop,
                        iteration=i,
                        latency_ms=0.0,
                        status="error",
                        error=str(e),
                    )
                )

        logger.info("[%s] %s traversal complete.", adapter.name, hop)
