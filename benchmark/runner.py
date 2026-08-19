"""
Benchmark runner — the main orchestrator.

This module is database-agnostic: it talks only to the
GraphDatabaseAdapter interface.  It handles the lifecycle:

  1. Connect
  2. Clear + create indexes
  3. Load data
  4. Warm up (done inside each workload)
  5. Run benchmarks
  6. Save raw results
  7. Generate processed results
"""

import json
import logging
import os
import time
from typing import Dict, List, Tuple

from benchmark.metrics import MetricsCollector
from benchmark.statistics import compute_stats
from benchmark.utils import time_operation
from config import BenchmarkConfig
from databases.base import GraphDatabaseAdapter
from workloads.aggregation import run_aggregation_benchmark
from workloads.lookup import run_lookup_benchmark
from workloads.mixed import run_mixed_benchmark
from workloads.traversal import run_traversal_benchmark

logger = logging.getLogger("benchmark.runner")


def _load_data(
    adapter: GraphDatabaseAdapter,
    node_ids: List[int],
    relationships: List[Tuple[int, int]],
    collector: MetricsCollector,
) -> None:
    """Clear database, create indexes, load nodes and relationships."""
    logger.info("[%s] Clearing database ...", adapter.name)
    adapter.clear_database()

    logger.info("[%s] Creating indexes ...", adapter.name)
    adapter.create_indexes()

    # Time node loading
    logger.info("[%s] Loading %d nodes ...", adapter.name, len(node_ids))
    start = time.perf_counter()
    adapter.load_nodes(node_ids)
    node_load_ms = (time.perf_counter() - start) * 1000.0

    # Time relationship loading
    logger.info(
        "[%s] Loading %d relationships ...", adapter.name, len(relationships)
    )
    start = time.perf_counter()
    adapter.load_relationships(relationships)
    rel_load_ms = (time.perf_counter() - start) * 1000.0

    total_load_ms = node_load_ms + rel_load_ms

    # Verify loaded counts
    actual_nodes = adapter.get_node_count()
    actual_rels = adapter.get_relationship_count()
    logger.info(
        "[%s] Loaded: %d nodes, %d relationships (expected: %d, %d)",
        adapter.name,
        actual_nodes,
        actual_rels,
        len(node_ids),
        len(relationships),
    )

    # Record load metrics
    nodes_per_sec = len(node_ids) / (node_load_ms / 1000.0) if node_load_ms > 0 else 0
    rels_per_sec = (
        len(relationships) / (rel_load_ms / 1000.0) if rel_load_ms > 0 else 0
    )

    from benchmark.metrics import Measurement

    collector.record(
        Measurement(
            database=adapter.name,
            workload="loading",
            query="total_load_time_ms",
            iteration=0,
            latency_ms=total_load_ms,
        )
    )
    collector.record(
        Measurement(
            database=adapter.name,
            workload="loading",
            query="nodes_per_second",
            iteration=0,
            latency_ms=nodes_per_sec,
        )
    )
    collector.record(
        Measurement(
            database=adapter.name,
            workload="loading",
            query="rels_per_second",
            iteration=0,
            latency_ms=rels_per_sec,
        )
    )


def generate_processed_results(
    collector: MetricsCollector,
    config: BenchmarkConfig,
    databases: List[str],
) -> List[Dict]:
    """
    Compute summary statistics from raw measurements.

    Returns a list of dicts suitable for writing to JSON/CSV.
    """
    import csv

    results = []

    workloads_queries = [
        ("traversal", "1hop"),
        ("traversal", "2hop"),
        ("traversal", "3hop"),
        ("lookup", "point_lookup"),
        ("lookup", "indexed_lookup"),
        ("aggregation", "degree_distribution"),
    ]

    for db in databases:
        # Load metrics (single values, not statistical)
        for query in ["total_load_time_ms", "nodes_per_second", "rels_per_second"]:
            values = collector.get_latencies(db, "loading", query)
            if values:
                results.append(
                    {
                        "database": db,
                        "workload": "loading",
                        "query": query,
                        "p50": values[0],
                        "p95": values[0],
                        "mean": values[0],
                        "min": values[0],
                        "max": values[0],
                        "iterations": 1,
                        "concurrency": 1,
                    }
                )

        # Standard workloads (with stats)
        for workload, query in workloads_queries:
            latencies = collector.get_latencies(db, workload, query)
            if latencies:
                stats = compute_stats(latencies)
                results.append(
                    {
                        "database": db,
                        "workload": workload,
                        "query": query,
                        "p50": round(stats["p50"], 3),
                        "p95": round(stats["p95"], 3),
                        "mean": round(stats["mean"], 3),
                        "min": round(stats["min"], 3),
                        "max": round(stats["max"], 3),
                        "iterations": stats["count"],
                        "concurrency": 1,
                    }
                )

        # Mixed workload (per concurrency level)
        for concurrency in config.concurrency_levels:
            # Throughput
            qps_values = collector.get_latencies(
                db, "mixed", "throughput_qps", concurrency
            )
            if qps_values:
                results.append(
                    {
                        "database": db,
                        "workload": "mixed",
                        "query": "throughput_qps",
                        "p50": qps_values[0],
                        "p95": qps_values[0],
                        "mean": qps_values[0],
                        "min": qps_values[0],
                        "max": qps_values[0],
                        "iterations": 1,
                        "concurrency": concurrency,
                    }
                )

            # Read latencies
            read_latencies = collector.get_latencies(
                db, "mixed", "read", concurrency
            )
            if read_latencies:
                stats = compute_stats(read_latencies)
                results.append(
                    {
                        "database": db,
                        "workload": "mixed",
                        "query": "read_latency",
                        "p50": round(stats["p50"], 3),
                        "p95": round(stats["p95"], 3),
                        "mean": round(stats["mean"], 3),
                        "min": round(stats["min"], 3),
                        "max": round(stats["max"], 3),
                        "iterations": stats["count"],
                        "concurrency": concurrency,
                    }
                )

            # Write latencies
            write_latencies = collector.get_latencies(
                db, "mixed", "write", concurrency
            )
            if write_latencies:
                stats = compute_stats(write_latencies)
                results.append(
                    {
                        "database": db,
                        "workload": "mixed",
                        "query": "write_latency",
                        "p50": round(stats["p50"], 3),
                        "p95": round(stats["p95"], 3),
                        "mean": round(stats["mean"], 3),
                        "min": round(stats["min"], 3),
                        "max": round(stats["max"], 3),
                        "iterations": stats["count"],
                        "concurrency": concurrency,
                    }
                )

    # Save to JSON and CSV
    os.makedirs(config.results_processed_dir, exist_ok=True)

    json_path = os.path.join(config.results_processed_dir, "processed_results.json")
    with open(json_path, "w") as fh:
        json.dump(results, fh, indent=2)
    logger.info("Processed results saved to %s", json_path)

    csv_path = os.path.join(config.results_processed_dir, "processed_results.csv")
    if results:
        with open(csv_path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        logger.info("Processed results saved to %s", csv_path)

    return results


def run_benchmark_for_adapter(
    adapter: GraphDatabaseAdapter,
    node_ids: List[int],
    relationships: List[Tuple[int, int]],
    config: BenchmarkConfig,
    collector: MetricsCollector,
) -> None:
    """Run the complete benchmark suite for a single database adapter."""
    logger.info("=" * 60)
    logger.info("BENCHMARKING: %s", adapter.name)
    logger.info("=" * 60)

    # Step 1: Load data
    _load_data(adapter, node_ids, relationships, collector)

    # Step 2: Traversals
    run_traversal_benchmark(adapter, node_ids, config, collector)

    # Step 3: Lookups
    run_lookup_benchmark(adapter, node_ids, config, collector)

    # Step 4: Aggregation
    run_aggregation_benchmark(adapter, config, collector)

    # Step 5: Mixed workload
    run_mixed_benchmark(adapter, node_ids, config, collector)

    # Step 6: Resource info
    resource_info = adapter.get_resource_info()
    logger.info("[%s] Resource info: %s", adapter.name, resource_info)

    # Save resource info
    os.makedirs(config.results_raw_dir, exist_ok=True)
    info_path = os.path.join(
        config.results_raw_dir, f"{adapter.name.lower()}_resource_info.json"
    )
    with open(info_path, "w") as fh:
        json.dump(resource_info, fh, indent=2)

    logger.info("[%s] Benchmark complete.", adapter.name)
