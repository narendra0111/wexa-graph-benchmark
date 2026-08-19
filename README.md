# CognoDB Cloud Graph Database Benchmark

A reproducible benchmark suite comparing five graph databases using the same public dataset, identical logical queries, and equivalent resource allocations.

## Executive Summary

> **NOTE**: This section will be populated with actual benchmark results after running the full suite. No numbers are fabricated — all performance data comes from measured benchmark runs.

## Databases Tested

| Database   | Type                   | Why Selected |
|------------|------------------------|--------------|
| CognoDB    | Cloud graph database   | Primary subject of this benchmark (assignment requirement) |
| Neo4j      | Native graph database  | Industry leader; the most widely adopted graph database |
| Memgraph   | In-memory graph DB     | High-performance in-memory engine; Bolt/Cypher compatible |
| FalkorDB   | Redis-based graph DB   | Ultra-low-latency graph queries on Redis infrastructure |
| ArangoDB   | Multi-model database   | Credible multi-model DB with native graph support (AQL) |

## Environment

| Property        | Value |
|-----------------|-------|
| Client machine  | _Populated at runtime_ |
| OS              | _Populated at runtime_ |
| Python version  | _Populated at runtime_ |
| Architecture    | _Populated at runtime_ |

## Resource Fairness

> [!IMPORTANT]
> Exact resource parity across all five platforms is not achievable because each vendor offers different free/entry-tier specifications.
> This section will document the actual vCPU, RAM, storage, and tier of each database instance used.

| Database | Tier | vCPU | RAM | Storage | Notes |
|----------|------|------|-----|---------|-------|
| CognoDB  | _TBD_ | _TBD_ | _TBD_ | _TBD_ | |
| Neo4j    | _TBD_ | _TBD_ | _TBD_ | _TBD_ | |
| Memgraph | _TBD_ | _TBD_ | _TBD_ | _TBD_ | |
| FalkorDB | _TBD_ | _TBD_ | _TBD_ | _TBD_ | |
| ArangoDB | _TBD_ | _TBD_ | _TBD_ | _TBD_ | |

## Dataset

| Property       | Value |
|----------------|-------|
| Source         | [SNAP soc-Pokec](https://snap.stanford.edu/data/soc-Pokec.html) |
| Download       | `https://snap.stanford.edu/data/soc-pokec-relationships.txt.gz` |
| Original nodes | 1,632,803 |
| Original rels  | 30,622,564 |
| Sampled rels   | 300,000 (random sample, seed=42) |
| Sampled nodes  | _Determined by sampled edges_ |
| Graph schema   | `(:Person {uid: INT})-[:KNOWS]->(:Person)` |

### Preprocessing

1. Download the compressed relationships file
2. Extract to tab-separated text
3. Parse (source, target) edge pairs
4. Randomly sample 300,000 edges (seed=42) to fit free-tier limits
5. Collect unique node IDs from sampled edges

## Methodology

| Parameter            | Value |
|----------------------|-------|
| Warm-up iterations   | 10 |
| Benchmark iterations | 100 |
| Random seed          | 42 |
| Traversal start nodes| 50 randomly selected |
| Concurrency levels   | 1, 10, 40 clients |
| Read/write ratio     | 80% reads / 20% writes |
| Mixed workload duration | 30 seconds per concurrency level |
| Timing method        | `time.perf_counter()` (wall-clock, high-resolution) |

## Workloads

### 1. Data Loading
- Bulk-create all nodes, then bulk-create all relationships
- Measure total load time, nodes/second, relationships/second

### 2. Traversals
```
-- Cypher (CognoDB, Neo4j, Memgraph, FalkorDB)
-- 1-hop:
MATCH (a:Person {uid: $uid})-[:KNOWS]->(b) RETURN b.uid
-- 2-hop:
MATCH (a:Person {uid: $uid})-[:KNOWS*2]->(b) RETURN DISTINCT b.uid
-- 3-hop:
MATCH (a:Person {uid: $uid})-[:KNOWS*3]->(b) RETURN DISTINCT b.uid

-- AQL (ArangoDB)
FOR v IN 1..1 OUTBOUND @start GRAPH "social" RETURN v.uid
FOR v IN 2..2 OUTBOUND @start GRAPH "social" RETURN DISTINCT v.uid
FOR v IN 3..3 OUTBOUND @start GRAPH "social" RETURN DISTINCT v.uid
```

### 3. Lookups
- **Point lookup**: Fetch one node by indexed `uid` property
- **Indexed lookup**: Range scan `uid >= min AND uid <= max` (range of 100)
- Indexed property: `Person.uid` on all databases

### 4. Aggregation
- Degree distribution: count nodes grouped by outgoing relationship count

### 5. Mixed Workload
- Concurrent threads performing 80% reads (point lookups) and 20% writes (create+delete relationship pairs)
- Tested at 1, 10, and 40 concurrent clients
- Each level runs for 30 seconds

## Results

> Results tables will be inserted here after running the benchmarks.

## Charts

> Charts will be inserted here after running the benchmarks.

## Analysis

> Analysis will be written after benchmarks produce actual data.

## Caveats

- **Cloud/network latency**: Results include network round-trip time to cloud-hosted databases
- **Free-tier throttling**: Some platforms may throttle free-tier instances under load
- **Resource differences**: Exact vCPU/RAM parity across all platforms is not achievable
- **Query language differences**: CognoDB/Neo4j/Memgraph/FalkorDB use Cypher; ArangoDB uses AQL — queries are logically equivalent but execution engines differ
- **Dataset sampling**: The full soc-Pokec dataset (30.6M edges) was sampled to 300k edges to fit free-tier storage limits

## Reproducibility

```bash
# 1. Clone the repository
git clone <repo-url> && cd wexa-graph-benchmark

# 2. Create virtual environment
python3 -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and fill in credentials
cp .env.example .env
# Edit .env with your database connection details

# 5. Run the full benchmark
python scripts/run_all.py
```

## Conclusion

> Conclusion will be written after benchmarks produce actual data. No winner will be forced — results will be presented honestly.

---

## Project Structure

```
wexa-graph-benchmark/
├── config.py              # Central configuration
├── databases/
│   ├── base.py            # Abstract adapter interface
│   ├── cognodb.py         # CognoDB adapter
│   ├── neo4j_adapter.py   # Neo4j adapter
│   ├── memgraph.py        # Memgraph adapter
│   ├── falkordb.py        # FalkorDB adapter
│   └── arangodb.py        # ArangoDB adapter
├── benchmark/
│   ├── runner.py           # Benchmark orchestrator
│   ├── metrics.py          # Measurement collection
│   ├── statistics.py       # p50/p95 computation
│   ├── charts.py           # Chart generation (matplotlib)
│   └── utils.py            # Logging, timing, env info
├── workloads/
│   ├── traversal.py        # 1/2/3-hop traversals
│   ├── lookup.py           # Point + indexed lookups
│   ├── aggregation.py      # Degree distribution
│   └── mixed.py            # Concurrent read/write
├── loaders/
│   └── load_dataset.py     # SNAP soc-Pokec downloader/parser
├── scripts/
│   ├── run_all.py          # Main entry point
│   └── inspect_dataset.py  # Dataset inspection utility
├── tests/
│   └── test_connectivity.py # Database connectivity tests
├── results/
│   ├── raw/                # Raw CSV measurements
│   ├── processed/          # Summary statistics (JSON + CSV)
│   └── charts/             # Generated PNG charts
├── .env.example            # Credential template
├── .gitignore
├── requirements.txt        # Pinned dependencies
└── README.md               # This file
```
