"""
Aggregation benchmark workload.

Measures a count/group-by style query: degree distribution
(count nodes grouped by their outgoing relationship count).
"""

import logging

from benchmark.metrics import Measurement, MetricsCollector
from benchmark.utils import time_operation
from config import BenchmarkConfig
from databases.base import GraphDatabaseAdapter

logger = logging.getLogger("benchmark.workloads.aggregation")


def run_aggregation_benchmark(
    adapter: GraphDatabaseAdapter,
    config: BenchmarkConfig,
    collector: MetricsCollector,
) -> None:
    """
    Run aggregation benchmark: degree distribution (count/group-by).
    """
    logger.info(
        "[%s] Running aggregation (warmup=%d, iterations=%d) ...",
        adapter.name,
        config.warmup_iterations,
        config.benchmark_iterations,
    )

    # Warm-up
    for _ in range(config.warmup_iterations):
        try:
            adapter.aggregation_count_by_group()
        except Exception as e:
            logger.warning("Warmup error (aggregation): %s", e)

    # Measurement
    for i in range(config.benchmark_iterations):
        try:
            elapsed_ms, _result = time_operation(
                adapter.aggregation_count_by_group
            )
            collector.record(
                Measurement(
                    database=adapter.name,
                    workload="aggregation",
                    query="degree_distribution",
                    iteration=i,
                    latency_ms=elapsed_ms,
                )
            )
        except Exception as e:
            collector.record(
                Measurement(
                    database=adapter.name,
                    workload="aggregation",
                    query="degree_distribution",
                    iteration=i,
                    latency_ms=0.0,
                    status="error",
                    error=str(e),
                )
            )

    logger.info("[%s] Aggregation complete.", adapter.name)
