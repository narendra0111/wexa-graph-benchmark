"""
Mixed workload benchmark.

Runs concurrent read and write operations to measure sustained
throughput under load.  Tests multiple concurrency levels
(default: 1, 10, 40 clients).

Read operations:   point lookups
Write operations:  create relationship, then delete it (net-neutral)
"""

import logging
import random
import threading
import time
from typing import List

from benchmark.metrics import Measurement, MetricsCollector
from config import BenchmarkConfig
from databases.base import GraphDatabaseAdapter

logger = logging.getLogger("benchmark.workloads.mixed")


def _worker(
    adapter: GraphDatabaseAdapter,
    node_ids: List[int],
    read_ratio: float,
    duration_seconds: int,
    seed: int,
    results: list,
    stop_event: threading.Event,
) -> None:
    """
    Worker thread that runs a mix of reads and writes.

    Appends (operation, latency_ms, status, error) tuples to *results*.
    """
    rng = random.Random(seed)
    while not stop_event.is_set():
        is_read = rng.random() < read_ratio
        node = rng.choice(node_ids)

        start = time.perf_counter()
        status = "ok"
        error = None

        try:
            if is_read:
                adapter.point_lookup(node)
            else:
                # Write: create a relationship then delete it (net-neutral)
                target = rng.choice(node_ids)
                adapter.write_create_relationship(node, target)
                adapter.write_delete_relationship(node, target)
        except Exception as e:
            status = "error"
            error = str(e)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        op = "read" if is_read else "write"
        results.append((op, elapsed_ms, status, error))


def run_mixed_benchmark(
    adapter: GraphDatabaseAdapter,
    node_ids: List[int],
    config: BenchmarkConfig,
    collector: MetricsCollector,
) -> None:
    """
    Run the mixed read/write workload at each concurrency level.

    For each concurrency level:
      1. Spawn N worker threads
      2. Let them run for config.mixed_duration_seconds
      3. Record queries/second and individual latencies
    """
    for concurrency in config.concurrency_levels:
        logger.info(
            "[%s] Mixed workload: concurrency=%d, duration=%ds, "
            "read_ratio=%.0f%%",
            adapter.name,
            concurrency,
            config.mixed_duration_seconds,
            config.mixed_read_write_ratio * 100,
        )

        all_results: list = []
        stop_event = threading.Event()
        threads = []

        for t in range(concurrency):
            thread = threading.Thread(
                target=_worker,
                args=(
                    adapter,
                    node_ids,
                    config.mixed_read_write_ratio,
                    config.mixed_duration_seconds,
                    config.random_seed + t,  # unique seed per thread
                    all_results,
                    stop_event,
                ),
                daemon=True,
            )
            threads.append(thread)

        # Start all threads
        for t in threads:
            t.start()

        # Let them run for the configured duration
        time.sleep(config.mixed_duration_seconds)
        stop_event.set()

        # Wait for threads to finish
        for t in threads:
            t.join(timeout=5)

        # Calculate throughput
        total_ops = len(all_results)
        qps = total_ops / config.mixed_duration_seconds if config.mixed_duration_seconds > 0 else 0

        logger.info(
            "[%s] Mixed workload (c=%d): %d ops in %ds = %.1f qps",
            adapter.name,
            concurrency,
            total_ops,
            config.mixed_duration_seconds,
            qps,
        )

        # Record individual measurements
        for i, (op, latency_ms, status, error) in enumerate(all_results):
            collector.record(
                Measurement(
                    database=adapter.name,
                    workload="mixed",
                    query=op,
                    iteration=i,
                    latency_ms=latency_ms,
                    status=status,
                    error=error,
                    concurrency=concurrency,
                )
            )

        # Record throughput as a special measurement
        collector.record(
            Measurement(
                database=adapter.name,
                workload="mixed",
                query="throughput_qps",
                iteration=0,
                latency_ms=qps,  # repurpose latency_ms for qps value
                concurrency=concurrency,
            )
        )
