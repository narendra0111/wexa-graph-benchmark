"""
Benchmark configuration.

All tuneable parameters live here so they can be changed in one place
without editing benchmark code.  Values can be overridden via environment
variables (see .env.example).
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class BenchmarkConfig:
    """Central configuration for the entire benchmark suite."""

    # ── Dataset ──────────────────────────────────────────────────────────
    dataset_url: str = (
        "https://snap.stanford.edu/data/soc-pokec-relationships.txt.gz"
    )
    dataset_dir: str = "data"
    dataset_file: str = "soc-pokec-relationships.txt"

    # ── Benchmark parameters ─────────────────────────────────────────────
    random_seed: int = 42
    warmup_iterations: int = 10
    benchmark_iterations: int = 100
    traversal_sample_nodes: int = 50  # number of random start nodes

    # ── Concurrency (mixed workload) ─────────────────────────────────────
    concurrency_levels: List[int] = field(default_factory=lambda: [1, 10, 40])
    mixed_read_write_ratio: float = 0.8  # 80 % reads, 20 % writes
    mixed_duration_seconds: int = 30  # run mixed workload for this long

    # ── Which databases to benchmark ─────────────────────────────────────
    enabled_databases: List[str] = field(
        default_factory=lambda: [
            "cognodb",
            "neo4j",
            "memgraph",
            "falkordb",
            "arangodb",
        ]
    )

    # ── Output paths ─────────────────────────────────────────────────────
    results_raw_dir: str = "results/raw"
    results_processed_dir: str = "results/processed"
    results_charts_dir: str = "results/charts"

    # ── Logging ──────────────────────────────────────────────────────────
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        """Allow environment-variable overrides for key settings."""
        self.random_seed = int(os.getenv("BENCH_RANDOM_SEED", self.random_seed))
        self.warmup_iterations = int(
            os.getenv("BENCH_WARMUP_ITERATIONS", self.warmup_iterations)
        )
        self.benchmark_iterations = int(
            os.getenv("BENCH_ITERATIONS", self.benchmark_iterations)
        )
        self.mixed_duration_seconds = int(
            os.getenv("BENCH_MIXED_DURATION", self.mixed_duration_seconds)
        )
        self.log_level = os.getenv("BENCH_LOG_LEVEL", self.log_level)

        env_dbs = os.getenv("BENCH_ENABLED_DATABASES")
        if env_dbs:
            self.enabled_databases = [
                db.strip() for db in env_dbs.split(",") if db.strip()
            ]
