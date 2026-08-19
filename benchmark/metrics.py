"""
Metrics collection.

Each benchmark measurement is stored as a Measurement dataclass.
The MetricsCollector accumulates measurements and can flush them to
CSV files in the raw results directory.
"""

import csv
import os
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class Measurement:
    """A single benchmark measurement."""

    database: str
    workload: str
    query: str
    iteration: int
    latency_ms: float
    status: str = "ok"           # "ok", "error", "timeout"
    error: Optional[str] = None
    concurrency: int = 1
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class MetricsCollector:
    """Accumulates Measurement objects and writes them to CSV."""

    measurements: List[Measurement] = field(default_factory=list)

    def record(self, m: Measurement) -> None:
        """Add a measurement."""
        self.measurements.append(m)

    def save_csv(self, output_dir: str, filename: str = "raw_results.csv") -> str:
        """Write all measurements to a CSV file.  Returns the file path."""
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, filename)

        fieldnames = [
            "database",
            "workload",
            "query",
            "iteration",
            "latency_ms",
            "status",
            "error",
            "concurrency",
            "timestamp",
        ]

        with open(path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for m in self.measurements:
                writer.writerow(asdict(m))

        return path

    def get_latencies(
        self, database: str, workload: str, query: str, concurrency: int = 1
    ) -> List[float]:
        """Return latency values for a specific (database, workload, query) slice."""
        return [
            m.latency_ms
            for m in self.measurements
            if m.database == database
            and m.workload == workload
            and m.query == query
            and m.concurrency == concurrency
            and m.status == "ok"
        ]

    def get_errors(self, database: str) -> List[Measurement]:
        """Return all error/timeout measurements for a database."""
        return [
            m
            for m in self.measurements
            if m.database == database and m.status != "ok"
        ]

    def clear(self) -> None:
        self.measurements.clear()
