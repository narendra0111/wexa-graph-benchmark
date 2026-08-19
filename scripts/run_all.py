#!/usr/bin/env python3
"""
Main entry point: run the full benchmark suite.

Usage:
    python scripts/run_all.py

This script:
  1. Validates configuration
  2. Loads and validates the dataset
  3. Connects to each configured database
  4. Loads data into each database
  5. Creates required indexes
  6. Runs all benchmark workloads
  7. Saves raw results (CSV)
  8. Calculates summary statistics
  9. Generates processed results (JSON + CSV)
  10. Generates charts (PNG)
  11. Prints a final summary
"""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
import time

from dotenv import load_dotenv

load_dotenv()

from benchmark.charts import generate_all_charts
from benchmark.metrics import MetricsCollector
from benchmark.runner import generate_processed_results, run_benchmark_for_adapter
from benchmark.utils import get_environment_info, setup_logging
from config import BenchmarkConfig
from loaders.load_dataset import load_dataset

# Maximum relationships to load (keep in 100k–500k range for free tiers)
MAX_RELATIONSHIPS = 300_000


def get_adapter(db_name: str):
    """Dynamically import and return the adapter for a database."""
    if db_name == "cognodb":
        from databases.cognodb import CognoDBAdapter
        return CognoDBAdapter()
    elif db_name == "neo4j":
        from databases.neo4j_adapter import Neo4jAdapter
        return Neo4jAdapter()
    elif db_name == "memgraph":
        from databases.memgraph import MemgraphAdapter
        return MemgraphAdapter()
    elif db_name == "falkordb":
        from databases.falkordb import FalkorDBAdapter
        return FalkorDBAdapter()
    elif db_name == "arangodb":
        from databases.arangodb import ArangoDBAdapter
        return ArangoDBAdapter()
    else:
        raise ValueError(f"Unknown database: {db_name}")


def main():
    config = BenchmarkConfig()
    logger = setup_logging(config)

    print("=" * 60)
    print("  CognoDB Cloud Graph Database Benchmark")
    print("=" * 60)

    # ── Step 1: Validate configuration ───────────────────────────────────
    logger.info("Step 1/11: Validating configuration ...")
    logger.info("  Enabled databases: %s", config.enabled_databases)
    logger.info("  Random seed: %d", config.random_seed)
    logger.info("  Warmup iterations: %d", config.warmup_iterations)
    logger.info("  Benchmark iterations: %d", config.benchmark_iterations)
    logger.info("  Concurrency levels: %s", config.concurrency_levels)
    logger.info("  Mixed R/W ratio: %.0f%% reads", config.mixed_read_write_ratio * 100)

    # ── Step 2: Load and validate dataset ────────────────────────────────
    logger.info("Step 2/11: Loading dataset ...")
    node_ids, edges = load_dataset(config, max_relationships=MAX_RELATIONSHIPS)
    logger.info(
        "  Dataset: %d nodes, %d relationships",
        len(node_ids),
        len(edges),
    )
    assert len(edges) >= 100_000, (
        f"Dataset has only {len(edges)} relationships (need ≥ 100,000)"
    )
    logger.info("  ✓ Dataset satisfies minimum 100,000 relationships requirement.")

    # Save dataset metadata
    os.makedirs(config.results_raw_dir, exist_ok=True)
    dataset_meta = {
        "source": "SNAP soc-Pokec",
        "url": config.dataset_url,
        "original_nodes": "1,632,803",
        "original_relationships": "30,622,564",
        "sampled_nodes": len(node_ids),
        "sampled_relationships": len(edges),
        "max_relationships_setting": MAX_RELATIONSHIPS,
        "random_seed": config.random_seed,
    }
    with open(os.path.join(config.results_raw_dir, "dataset_metadata.json"), "w") as fh:
        json.dump(dataset_meta, fh, indent=2)

    # ── Step 3–8: Benchmark each database ────────────────────────────────
    collector = MetricsCollector()
    env_info = get_environment_info()
    successful_dbs = []
    failed_dbs = []

    overall_start = time.perf_counter()

    for db_name in config.enabled_databases:
        logger.info("Step 3–8: Benchmarking %s ...", db_name)

        try:
            adapter = get_adapter(db_name)
            adapter.connect()

            run_benchmark_for_adapter(
                adapter, node_ids, edges, config, collector
            )

            adapter.close()
            successful_dbs.append(db_name)

        except Exception as e:
            logger.error(
                "FAILED to benchmark %s: %s — marking as unavailable.",
                db_name,
                e,
            )
            failed_dbs.append((db_name, str(e)))

    overall_elapsed = time.perf_counter() - overall_start

    # ── Step 9: Save raw results ─────────────────────────────────────────
    logger.info("Step 9/11: Saving raw results ...")
    raw_path = collector.save_csv(config.results_raw_dir)
    logger.info("  Raw results: %s (%d measurements)", raw_path, len(collector.measurements))

    # ── Step 10: Generate processed results ──────────────────────────────
    logger.info("Step 10/11: Generating processed results ...")
    processed = generate_processed_results(collector, config, successful_dbs)

    # ── Step 11: Generate charts ─────────────────────────────────────────
    logger.info("Step 11/11: Generating charts ...")
    processed_json = os.path.join(config.results_processed_dir, "processed_results.json")
    if os.path.exists(processed_json):
        generate_all_charts(processed_json, config.results_charts_dir)
    else:
        logger.warning("No processed results found — skipping chart generation.")

    # ── Final Summary ────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  BENCHMARK COMPLETE")
    print("=" * 60)
    print(f"  Total time:           {overall_elapsed:.1f}s")
    print(f"  Total measurements:   {len(collector.measurements)}")
    print(f"  Databases tested:     {', '.join(successful_dbs) or 'none'}")
    if failed_dbs:
        print(f"  Databases failed:     {', '.join(db for db, _ in failed_dbs)}")
        for db, reason in failed_dbs:
            print(f"    {db}: {reason}")
    print()
    print(f"  Raw results:          {config.results_raw_dir}/")
    print(f"  Processed results:    {config.results_processed_dir}/")
    print(f"  Charts:               {config.results_charts_dir}/")
    print()
    print(f"  Client machine:       {env_info['machine']}")
    print(f"  OS:                   {env_info['os']}")
    print(f"  Python:               {env_info['python_version']}")
    print("=" * 60)

    # Save environment info
    with open(os.path.join(config.results_raw_dir, "environment.json"), "w") as fh:
        json.dump(env_info, fh, indent=2)

    # Save failure report
    if failed_dbs:
        with open(os.path.join(config.results_raw_dir, "failures.json"), "w") as fh:
            json.dump(
                [{"database": db, "error": reason} for db, reason in failed_dbs],
                fh,
                indent=2,
            )

    return 0 if not failed_dbs else 1


if __name__ == "__main__":
    sys.exit(main())
