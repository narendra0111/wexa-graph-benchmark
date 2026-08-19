"""
Dataset acquisition and preprocessing for the SNAP soc-Pokec dataset.

The soc-Pokec dataset is a social network from a Slovak social platform.
Source: https://snap.stanford.edu/data/soc-Pokec.html

The relationships file contains directed edges (friendships) as tab-
separated pairs of user IDs.

This module handles:
  1. Downloading the compressed dataset
  2. Extracting it
  3. Parsing edges into (source, target) tuples
  4. Collecting unique node IDs
  5. Optionally sampling to fit free-tier size limits
"""

import gzip
import logging
import os
import random
import urllib.request
from typing import List, Set, Tuple

from config import BenchmarkConfig

logger = logging.getLogger("benchmark.loader")


def download_dataset(config: BenchmarkConfig) -> str:
    """
    Download the soc-pokec-relationships.txt.gz file if not already present.

    Returns the path to the extracted .txt file.
    """
    os.makedirs(config.dataset_dir, exist_ok=True)

    gz_path = os.path.join(config.dataset_dir, "soc-pokec-relationships.txt.gz")
    txt_path = os.path.join(config.dataset_dir, config.dataset_file)

    # If already extracted, skip
    if os.path.exists(txt_path):
        logger.info("Dataset already exists at %s — skipping download.", txt_path)
        return txt_path

    # Download
    if not os.path.exists(gz_path):
        logger.info("Downloading dataset from %s ...", config.dataset_url)
        urllib.request.urlretrieve(config.dataset_url, gz_path)
        logger.info("Download complete: %s", gz_path)
    else:
        logger.info("Compressed file already exists at %s", gz_path)

    # Extract
    logger.info("Extracting %s ...", gz_path)
    with gzip.open(gz_path, "rt", encoding="utf-8") as gz_in:
        with open(txt_path, "w", encoding="utf-8") as txt_out:
            for line in gz_in:
                txt_out.write(line)
    logger.info("Extraction complete: %s", txt_path)

    return txt_path


def parse_edges(filepath: str) -> List[Tuple[int, int]]:
    """
    Parse the soc-pokec-relationships.txt file.

    Each non-comment line contains two tab-separated node IDs.
    Returns a list of (source_id, target_id) tuples.
    """
    edges: List[Tuple[int, int]] = []
    logger.info("Parsing edges from %s ...", filepath)

    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    src, tgt = int(parts[0]), int(parts[1])
                    edges.append((src, tgt))
                except ValueError:
                    continue

    logger.info("Parsed %d edges.", len(edges))
    return edges


def collect_node_ids(edges: List[Tuple[int, int]]) -> List[int]:
    """Extract a sorted list of unique node IDs from edges."""
    node_set: Set[int] = set()
    for src, tgt in edges:
        node_set.add(src)
        node_set.add(tgt)
    nodes = sorted(node_set)
    logger.info("Found %d unique nodes.", len(nodes))
    return nodes


def sample_dataset(
    edges: List[Tuple[int, int]],
    max_relationships: int,
    seed: int = 42,
) -> List[Tuple[int, int]]:
    """
    If the dataset exceeds *max_relationships*, randomly sample down.

    Uses a fixed seed for reproducibility.
    """
    if len(edges) <= max_relationships:
        logger.info(
            "Dataset has %d edges (≤ %d) — no sampling needed.",
            len(edges),
            max_relationships,
        )
        return edges

    logger.info(
        "Sampling %d edges from %d (seed=%d).",
        max_relationships,
        len(edges),
        seed,
    )
    rng = random.Random(seed)
    return rng.sample(edges, max_relationships)


def load_dataset(
    config: BenchmarkConfig,
    max_relationships: int | None = None,
) -> Tuple[List[int], List[Tuple[int, int]]]:
    """
    High-level entry point: download, parse, (optionally sample), return.

    Returns (node_ids, edges).
    """
    txt_path = download_dataset(config)
    edges = parse_edges(txt_path)

    if max_relationships is not None:
        edges = sample_dataset(edges, max_relationships, config.random_seed)

    nodes = collect_node_ids(edges)
    return nodes, edges
