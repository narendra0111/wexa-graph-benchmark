"""
Shared utility functions for the benchmark suite.
"""

import logging
import os
import platform
import sys
import time
from typing import Callable, Tuple

from config import BenchmarkConfig


def setup_logging(config: BenchmarkConfig) -> logging.Logger:
    """Configure and return the root benchmark logger."""
    logger = logging.getLogger("benchmark")
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return logger


def time_operation(func: Callable, *args, **kwargs) -> Tuple[float, object]:
    """
    Time a callable and return (elapsed_ms, result).

    Uses time.perf_counter for high-resolution wall-clock timing.
    """
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return elapsed_ms, result


def get_environment_info() -> dict:
    """Collect client-machine metadata for the results report."""
    return {
        "machine": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
    }
