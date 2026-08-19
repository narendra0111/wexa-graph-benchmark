"""
Statistics helpers for computing p50, p95, and other summary stats
from raw latency measurements.
"""

from typing import Dict, List

import numpy as np


def compute_stats(latencies_ms: List[float]) -> Dict[str, float]:
    """
    Compute summary statistics from a list of latency measurements.

    Returns a dict with keys: p50, p95, mean, min, max, count.
    """
    if not latencies_ms:
        return {
            "p50": 0.0,
            "p95": 0.0,
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "count": 0,
        }
    arr = np.array(latencies_ms, dtype=np.float64)
    return {
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "mean": float(np.mean(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "count": len(latencies_ms),
    }
