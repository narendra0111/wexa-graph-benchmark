#!/usr/bin/env python3
"""
Download and inspect the SNAP soc-Pokec dataset.

Run:  python scripts/inspect_dataset.py

This will download the dataset (if not cached), parse it, and print
the exact node count and relationship count.
"""

import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from config import BenchmarkConfig
from loaders.load_dataset import download_dataset, parse_edges, collect_node_ids

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    config = BenchmarkConfig()

    print("=" * 60)
    print("SNAP soc-Pokec Dataset Inspection")
    print("=" * 60)

    txt_path = download_dataset(config)
    edges = parse_edges(txt_path)
    nodes = collect_node_ids(edges)

    print()
    print(f"  File:           {txt_path}")
    print(f"  Nodes:          {len(nodes):>12,}")
    print(f"  Relationships:  {len(edges):>12,}")
    print()

    if len(edges) >= 100_000:
        print("  ✓ Satisfies minimum 100,000 relationships requirement.")
    else:
        print("  ✗ WARNING: Dataset has fewer than 100,000 relationships!")

    print()
    print("  First 5 edges:", edges[:5])
    print("  Node ID range:", min(nodes), "–", max(nodes))
    print("=" * 60)


if __name__ == "__main__":
    main()
