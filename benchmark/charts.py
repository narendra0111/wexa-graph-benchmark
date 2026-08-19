"""
Chart generation using matplotlib only.

Reads processed results and produces PNG charts for:
  1. Load throughput (nodes/s, rels/s)
  2. 1-hop latency
  3. 2-hop latency
  4. 3-hop latency
  5. Lookup latency
  6. Aggregation latency
  7. Mixed workload throughput
  8. Concurrency vs throughput
"""

import json
import logging
import os
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt

logger = logging.getLogger("benchmark.charts")

# Consistent color palette for databases
DB_COLORS = {
    "CognoDB": "#2196F3",
    "Neo4j": "#008CC1",
    "Memgraph": "#F7941D",
    "FalkorDB": "#E53935",
    "ArangoDB": "#68B723",
}


def _get_color(db_name: str) -> str:
    return DB_COLORS.get(db_name, "#9E9E9E")


def _filter(data: List[Dict], workload: str, query: str, concurrency: int = 1) -> List[Dict]:
    """Filter processed results by workload, query, and concurrency."""
    return [
        r for r in data
        if r["workload"] == workload
        and r["query"] == query
        and r.get("concurrency", 1) == concurrency
    ]


def _save_fig(fig, output_dir: str, name: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("Chart saved: %s", path)
    return path


def chart_load_throughput(data: List[Dict], output_dir: str) -> None:
    """Bar chart comparing load throughput (nodes/s and rels/s)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Data Loading Throughput", fontsize=14, fontweight="bold")

    for ax, query, title in [
        (ax1, "nodes_per_second", "Nodes / Second"),
        (ax2, "rels_per_second", "Relationships / Second"),
    ]:
        rows = _filter(data, "loading", query)
        dbs = [r["database"] for r in rows]
        vals = [r["mean"] for r in rows]
        colors = [_get_color(db) for db in dbs]

        ax.bar(dbs, vals, color=colors)
        ax.set_title(title)
        ax.set_ylabel("Throughput")
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8)

    _save_fig(fig, output_dir, "load_throughput")


def _chart_latency(
    data: List[Dict],
    workload: str,
    query: str,
    title: str,
    output_dir: str,
    filename: str,
) -> None:
    """Grouped bar chart for p50/p95 latency."""
    rows = _filter(data, workload, query)
    if not rows:
        logger.warning("No data for %s/%s — skipping chart.", workload, query)
        return

    dbs = [r["database"] for r in rows]
    p50s = [r["p50"] for r in rows]
    p95s = [r["p95"] for r in rows]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(dbs))
    width = 0.35

    bars1 = ax.bar([i - width / 2 for i in x], p50s, width, label="p50", alpha=0.85)
    bars2 = ax.bar([i + width / 2 for i in x], p95s, width, label="p95", alpha=0.85)

    # Color each bar group by database
    for i, db in enumerate(dbs):
        color = _get_color(db)
        bars1[i].set_color(color)
        bars2[i].set_color(color)
        bars2[i].set_alpha(0.5)

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Latency (ms)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(dbs)
    ax.legend()

    _save_fig(fig, output_dir, filename)


def chart_traversals(data: List[Dict], output_dir: str) -> None:
    """Generate separate charts for 1-hop, 2-hop, 3-hop traversals."""
    for hop in ["1hop", "2hop", "3hop"]:
        _chart_latency(
            data, "traversal", hop,
            f"{hop.replace('hop', '-Hop')} Traversal Latency",
            output_dir, f"traversal_{hop}",
        )


def chart_lookups(data: List[Dict], output_dir: str) -> None:
    """Generate charts for point lookup and indexed lookup."""
    _chart_latency(
        data, "lookup", "point_lookup",
        "Point Lookup Latency",
        output_dir, "lookup_point",
    )
    _chart_latency(
        data, "lookup", "indexed_lookup",
        "Indexed / Filtered Lookup Latency",
        output_dir, "lookup_indexed",
    )


def chart_aggregation(data: List[Dict], output_dir: str) -> None:
    """Generate chart for aggregation (degree distribution)."""
    _chart_latency(
        data, "aggregation", "degree_distribution",
        "Aggregation (Degree Distribution) Latency",
        output_dir, "aggregation",
    )


def chart_mixed_throughput(data: List[Dict], output_dir: str) -> None:
    """Bar chart of mixed workload throughput at each concurrency level."""
    rows = [r for r in data if r["workload"] == "mixed" and r["query"] == "throughput_qps"]
    if not rows:
        logger.warning("No mixed workload data — skipping chart.")
        return

    # Group by concurrency
    concurrency_levels = sorted(set(r["concurrency"] for r in rows))

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle("Mixed Workload Throughput", fontsize=14, fontweight="bold")

    dbs = sorted(set(r["database"] for r in rows))
    width = 0.8 / len(dbs)

    for j, db in enumerate(dbs):
        vals = []
        for c in concurrency_levels:
            matching = [r for r in rows if r["database"] == db and r["concurrency"] == c]
            vals.append(matching[0]["mean"] if matching else 0)

        positions = [i + j * width for i in range(len(concurrency_levels))]
        ax.bar(positions, vals, width, label=db, color=_get_color(db))

    ax.set_xlabel("Concurrency")
    ax.set_ylabel("Queries / Second")
    ax.set_xticks([i + width * (len(dbs) - 1) / 2 for i in range(len(concurrency_levels))])
    ax.set_xticklabels([str(c) for c in concurrency_levels])
    ax.legend()

    _save_fig(fig, output_dir, "mixed_throughput")


def chart_concurrency_vs_throughput(data: List[Dict], output_dir: str) -> None:
    """Line chart: concurrency on x-axis, throughput on y-axis, one line per DB."""
    rows = [r for r in data if r["workload"] == "mixed" and r["query"] == "throughput_qps"]
    if not rows:
        return

    dbs = sorted(set(r["database"] for r in rows))
    concurrency_levels = sorted(set(r["concurrency"] for r in rows))

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.suptitle("Concurrency vs Throughput", fontsize=14, fontweight="bold")

    for db in dbs:
        db_rows = sorted(
            [r for r in rows if r["database"] == db],
            key=lambda r: r["concurrency"],
        )
        xs = [r["concurrency"] for r in db_rows]
        ys = [r["mean"] for r in db_rows]
        ax.plot(xs, ys, marker="o", label=db, color=_get_color(db), linewidth=2)

    ax.set_xlabel("Concurrency (# clients)")
    ax.set_ylabel("Queries / Second")
    ax.legend()
    ax.grid(True, alpha=0.3)

    _save_fig(fig, output_dir, "concurrency_vs_throughput")


def generate_all_charts(processed_results_path: str, output_dir: str) -> None:
    """Load processed results and generate all charts."""
    with open(processed_results_path, "r") as fh:
        data = json.load(fh)

    logger.info("Generating charts from %d result rows ...", len(data))

    chart_load_throughput(data, output_dir)
    chart_traversals(data, output_dir)
    chart_lookups(data, output_dir)
    chart_aggregation(data, output_dir)
    chart_mixed_throughput(data, output_dir)
    chart_concurrency_vs_throughput(data, output_dir)

    logger.info("All charts generated in %s", output_dir)
