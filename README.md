# CognoDB Cloud Graph Database Benchmark

A reproducible benchmark suite comparing five graph databases using the same public dataset, identical logical queries, and comparable benchmark configurations.

## Executive Summary

> **Benchmark completed:** The suite successfully completed the full workload set for Memgraph, FalkorDB, and ArangoDB. CognoDB and Neo4j were recorded as failed/unavailable during data loading, with the exact errors documented below. All reported performance figures come directly from the measured benchmark run.

### Data Loading

| Database | Total Load Time (s) | Nodes/sec | Rels/sec |
|----------|---------------------|-----------|----------|
| CognoDB  | _Failed_ | _Failed_ | _Failed_ |
| Neo4j    | _Failed_ | _Failed_ | _Failed_ |
| Memgraph | 834.5 | 755.5 | 976.4 |
| FalkorDB | 18.6 | 183979.6 | 18217.3 |
| ArangoDB | 589.6 | 1278.8 | 1078.7 |

### Traversals & Lookups (p95 latency in ms)

| Database | Point Lookup | 1-Hop Traversal | 2-Hop Traversal | 3-Hop Traversal |
|----------|--------------|-----------------|-----------------|-----------------|
| CognoDB  | - | - | - | - |
| Neo4j    | - | - | - | - |
| Memgraph | 788.10 | 717.59 | 630.14 | 626.74 |
| FalkorDB | 0.35 | 0.33 | 0.33 | 3.13 |
| ArangoDB | 550.77 | 446.19 | 498.74 | 512.07 |

### Analytics / Aggregation

| Database | Degree Distribution (p95 ms) |
|----------|------------------------------|
| CognoDB  | - |
| Neo4j    | - |
| Memgraph | 1462.74 |
| FalkorDB | 913.32 |
| ArangoDB | 6458.39 |

### Concurrent Mixed Workload (Throughput / QPS)

| Database | Concurrency: 1 | Concurrency: 10 | Concurrency: 40 |
|----------|----------------|-----------------|-----------------|
| CognoDB  | - | - | - |
| Neo4j    | - | - | - |
| Memgraph | 1.76 | 19.16 | 67.33 |
| FalkorDB | 242.8 | 1453.5 | 4273.6 |
| ArangoDB | 2.30 | 15.70 | 54.86 |

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
| Client machine  | Narendras-MacBook-Air.local |
| OS              | Darwin 25.6.0 |
| Python version  | 3.14.6 |
| Architecture    | arm64 |

## Resource Fairness

> [!IMPORTANT]
> Exact resource parity across all five platforms is not achievable because each vendor offers different free/entry-tier specifications.
> The table below documents the configured tier and known resource characteristics of each database instance used.

| Database | Tier | vCPU | RAM | Storage | Notes |
|----------|------|------|-----|---------|-------|
| CognoDB  | Free Cloud | 0.5 (burstable) | 512 MB | 1 GB | Primary subject |
| Neo4j    | Aura Free | Shared | Abstract | Abstract | Strict limit of 400k relationships |
| Memgraph | Cloud Trial | Shared | 2 GB | Included | Expires in 14 days |
| FalkorDB | Docker (Local) | 1 | 512 MB | Local | Cloud free tier (100MB) too small; self-hosted locally to match CognoDB RAM |
| ArangoDB | Free Trial | Configurable | ~4 GB | Included | Gives significant hardware advantage over CognoDB |

## Dataset

| Property       | Value |
|----------------|-------|
| Source         | [SNAP soc-Pokec](https://snap.stanford.edu/data/soc-Pokec.html) |
| Download       | `https://snap.stanford.edu/data/soc-pokec-relationships.txt.gz` |
| Original nodes | 1,632,803 |
| Original rels  | 30,622,564 |
| Sampled rels   | 300,000 (random sample, seed=42) |
| Sampled nodes  | 398,372 |
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

The benchmark produced measured results for Memgraph, FalkorDB, and ArangoDB. CognoDB and Neo4j are documented as failed during data loading.

## Charts

Generated charts are available in [`results/charts/`](results/charts/).

## Analysis & Conclusions

### Failures and Honest Caveats
1. **Neo4j Aura Free limit exceeded**: Despite sampling the dataset down to 300,000 edges to fit Neo4j's 400,000 relationship limit, the dataset yielded 398,372 unique nodes. Neo4j strictly limits nodes to 200,000 on its free tier, so the data load failed and Neo4j was excluded from the run.
2. **CognoDB Disconnection**: CognoDB's connection dropped mid-benchmark ("Failed to read from defunct connection"). The free cloud tier could not sustain the ingestion/query workload.
3. **FalkorDB Local Advantage & Initial OOM**: FalkorDB was run locally via Docker rather than the cloud (to avoid its 100MB cloud memory limit). This gave it an inherent 0ms network latency advantage, artificially inflating its QPS and lowering its latency compared to Memgraph and ArangoDB (which suffered from cloud HTTP/Bolt round-trip times). During an initial test, FalkorDB OOM'd at 512 MB RAM during the mixed workload, requiring a container restart, demonstrating the vulnerability of in-memory stores under strict constraints.

### Performance Conclusions
- **ArangoDB vs Memgraph**: ArangoDB provided faster load times and better traversal latencies across the board, but struggled with degree aggregations compared to Memgraph. Mixed-workload throughput is reported in the generated benchmark results and charts.
- Both ArangoDB and Memgraph had a significantly higher RAM provision in their trial tiers (~4GB and 2GB respectively) compared to the 512MB we used for FalkorDB.

## Caveats

- **Cloud/network latency**: Results include network round-trip time to cloud-hosted databases (CognoDB, Neo4j, Memgraph).
- **FalkorDB network advantage**: Because FalkorDB's cloud free tier was strictly limited to 100MB RAM (which could OOM on our dataset), we elected to run FalkorDB via Docker locally with matched resources (512 MB RAM, 1 CPU). This gives FalkorDB an inherent latency advantage since it bypasses the internet, which must be considered when analyzing its latency numbers.
- **Free-tier throttling**: Some platforms may throttle free-tier instances under load.
- **Resource differences**: Exact vCPU/RAM parity across all platforms is not achievable, but we matched FalkorDB locally to CognoDB's 512 MB.
- **Query language differences**: CognoDB/Neo4j/Memgraph/FalkorDB use Cypher; ArangoDB uses AQL — queries are logically equivalent but execution engines differ.
- **Dataset sampling**: The full soc-Pokec dataset (30.6M edges) was sampled to 300k edges to fit free-tier storage limits.

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

> The benchmark shows that no single database can be declared the universal winner from this run. Memgraph, FalkorDB, and ArangoDB completed the full workload suite, while CognoDB and Neo4j could not load the complete 398,372-node dataset because of connection and tier limitations. FalkorDB achieved the highest observed throughput and lowest latency, but its local deployment removes cloud network latency and therefore is not directly comparable to the cloud-hosted databases. The results should be interpreted together with the documented resource and deployment differences.

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
