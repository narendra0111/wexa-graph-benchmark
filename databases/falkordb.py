"""
FalkorDB adapter.

FalkorDB is a Redis-based graph database that uses a subset of Cypher
(openCypher).  We use the official `falkordb` Python client.

Credentials: FALKORDB_HOST, FALKORDB_PORT, FALKORDB_PASSWORD
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from databases.base import GraphDatabaseAdapter

logger = logging.getLogger("benchmark.falkordb")

_BATCH_SIZE = 500
_GRAPH_NAME = "benchmark"


class FalkorDBAdapter(GraphDatabaseAdapter):
    """Adapter for FalkorDB (Cloud or self-hosted)."""

    name = "FalkorDB"

    def __init__(self) -> None:
        self._db = None
        self._graph = None

    # ── Connection ───────────────────────────────────────────────────────

    def connect(self) -> None:
        from falkordb import FalkorDB

        host = os.environ["FALKORDB_HOST"]
        port = int(os.environ.get("FALKORDB_PORT", 6379))
        password = os.environ.get("FALKORDB_PASSWORD", None)
        logger.info("Connecting to FalkorDB at %s:%d ...", host, port)
        self._db = FalkorDB(host=host, port=port, password=password)
        self._graph = self._db.select_graph(_GRAPH_NAME)
        # Quick connectivity check
        self._graph.query("RETURN 1")
        logger.info("FalkorDB connection verified.")

    def close(self) -> None:
        # falkordb client doesn't have an explicit close; connection
        # is managed by the underlying redis client.
        logger.info("FalkorDB connection closed (no-op).")

    # ── Schema / setup ───────────────────────────────────────────────────

    def clear_database(self) -> None:
        logger.info("Clearing FalkorDB graph '%s' ...", _GRAPH_NAME)
        try:
            self._graph.query("MATCH (n) DETACH DELETE n")
        except Exception:
            pass
        logger.info("FalkorDB database cleared.")

    def create_indexes(self) -> None:
        """Indexed property: Person.uid"""
        logger.info("Creating FalkorDB indexes ...")
        try:
            self._graph.query("CREATE INDEX FOR (p:Person) ON (p.uid)")
        except Exception:
            # Index may already exist
            pass
        logger.info("FalkorDB indexes created.")

    # ── Data loading ─────────────────────────────────────────────────────

    def load_nodes(self, node_ids: List[int]) -> None:
        logger.info("Loading %d nodes into FalkorDB ...", len(node_ids))
        for i in range(0, len(node_ids), _BATCH_SIZE):
            batch = node_ids[i : i + _BATCH_SIZE]
            self._graph.query(
                "UNWIND $ids AS id CREATE (p:Person {uid: id})",
                {"ids": batch},
            )
        logger.info("FalkorDB node loading complete.")

    def load_relationships(self, relationships: List[Tuple[int, int]]) -> None:
        logger.info("Loading %d relationships into FalkorDB ...", len(relationships))
        for i in range(0, len(relationships), _BATCH_SIZE):
            batch = [
                {"src": s, "tgt": t}
                for s, t in relationships[i : i + _BATCH_SIZE]
            ]
            self._graph.query(
                """
                UNWIND $rels AS r
                MATCH (a:Person {uid: r.src}), (b:Person {uid: r.tgt})
                CREATE (a)-[:KNOWS]->(b)
                """,
                {"rels": batch},
            )
        logger.info("FalkorDB relationship loading complete.")

    def get_node_count(self) -> int:
        result = self._graph.query("MATCH (n:Person) RETURN count(n) AS cnt")
        return result.result_set[0][0]

    def get_relationship_count(self) -> int:
        result = self._graph.query(
            "MATCH ()-[r:KNOWS]->() RETURN count(r) AS cnt"
        )
        return result.result_set[0][0]

    # ── Queries ──────────────────────────────────────────────────────────

    def traversal_1hop(self, start_node_id: int) -> List[int]:
        result = self._graph.query(
            "MATCH (a:Person {uid: $uid})-[:KNOWS]->(b) RETURN b.uid AS uid",
            {"uid": start_node_id},
        )
        return [row[0] for row in result.result_set]

    def traversal_2hop(self, start_node_id: int) -> List[int]:
        result = self._graph.query(
            "MATCH (a:Person {uid: $uid})-[:KNOWS*2]->(b) "
            "RETURN DISTINCT b.uid AS uid",
            {"uid": start_node_id},
        )
        return [row[0] for row in result.result_set]

    def traversal_3hop(self, start_node_id: int) -> List[int]:
        result = self._graph.query(
            "MATCH (a:Person {uid: $uid})-[:KNOWS*3]->(b) "
            "RETURN DISTINCT b.uid AS uid",
            {"uid": start_node_id},
        )
        return [row[0] for row in result.result_set]

    def point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        result = self._graph.query(
            "MATCH (p:Person {uid: $uid}) RETURN p.uid AS uid",
            {"uid": node_id},
        )
        if result.result_set:
            return {"uid": result.result_set[0][0]}
        return None

    def indexed_lookup(self, min_id: int, max_id: int) -> List[int]:
        result = self._graph.query(
            "MATCH (p:Person) WHERE p.uid >= $min AND p.uid <= $max "
            "RETURN p.uid AS uid",
            {"min": min_id, "max": max_id},
        )
        return [row[0] for row in result.result_set]

    def aggregation_count_by_group(self) -> List[Dict[str, Any]]:
        result = self._graph.query(
            """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:KNOWS]->()
            WITH p, count(r) AS degree
            RETURN degree, count(p) AS node_count
            ORDER BY degree
            """
        )
        return [
            {"degree": row[0], "node_count": row[1]}
            for row in result.result_set
        ]

    # ── Write operations ─────────────────────────────────────────────────

    def write_create_relationship(self, source_id: int, target_id: int) -> bool:
        try:
            self._graph.query(
                "MATCH (a:Person {uid: $src}), (b:Person {uid: $tgt}) "
                "CREATE (a)-[:KNOWS]->(b)",
                {"src": source_id, "tgt": target_id},
            )
            return True
        except Exception as e:
            logger.warning("Write failed: %s", e)
            return False

    def write_delete_relationship(self, source_id: int, target_id: int) -> bool:
        try:
            self._graph.query(
                "MATCH (a:Person {uid: $src})-[r:KNOWS]->(b:Person {uid: $tgt}) "
                "DELETE r",
                {"src": source_id, "tgt": target_id},
            )
            return True
        except Exception as e:
            logger.warning("Delete failed: %s", e)
            return False

    # ── Footprint ────────────────────────────────────────────────────────

    def get_resource_info(self) -> Dict[str, str]:
        return {
            "platform": "FalkorDB",
            "version": "Not observable",
            "instance_type": "Not observable",
            "vcpu": "Not observable",
            "ram": "Not observable",
            "storage": "Not observable",
        }
