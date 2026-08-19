"""
Memgraph adapter.

Memgraph also speaks Bolt + Cypher, so the driver and query patterns
are very similar to Neo4j / CognoDB.

Note: Memgraph uses slightly different index syntax than Neo4j.
We use the neo4j Python driver for Bolt connectivity (Memgraph is
Bolt-compatible) — the pymemgraph package listed in requirements.txt
is a lightweight wrapper; for consistency we use the neo4j driver
directly.

Credentials: MEMGRAPH_URI, MEMGRAPH_USERNAME, MEMGRAPH_PASSWORD
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from databases.base import GraphDatabaseAdapter

logger = logging.getLogger("benchmark.memgraph")

_BATCH_SIZE = 500


class MemgraphAdapter(GraphDatabaseAdapter):
    """Adapter for Memgraph (Cloud or self-hosted)."""

    name = "Memgraph"

    def __init__(self) -> None:
        self._driver = None

    # ── Connection ───────────────────────────────────────────────────────

    def connect(self) -> None:
        uri = os.environ["MEMGRAPH_URI"]
        user = os.environ.get("MEMGRAPH_USERNAME", "")
        password = os.environ.get("MEMGRAPH_PASSWORD", "")
        logger.info("Connecting to Memgraph at %s ...", uri)
        auth = (user, password) if user else None
        self._driver = GraphDatabase.driver(uri, auth=auth)
        self._driver.verify_connectivity()
        logger.info("Memgraph connection verified.")

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            logger.info("Memgraph connection closed.")

    # ── Schema / setup ───────────────────────────────────────────────────

    def clear_database(self) -> None:
        logger.info("Clearing Memgraph database ...")
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("Memgraph database cleared.")

    def create_indexes(self) -> None:
        """
        Indexed property: Person.uid

        Memgraph index syntax: CREATE INDEX ON :Person(uid)
        """
        logger.info("Creating Memgraph indexes ...")
        with self._driver.session() as session:
            try:
                session.run("CREATE INDEX ON :Person(uid)")
            except Neo4jError:
                # Index may already exist
                pass
        logger.info("Memgraph indexes created.")

    # ── Data loading ─────────────────────────────────────────────────────

    def load_nodes(self, node_ids: List[int]) -> None:
        logger.info("Loading %d nodes into Memgraph ...", len(node_ids))
        with self._driver.session() as session:
            for i in range(0, len(node_ids), _BATCH_SIZE):
                batch = node_ids[i : i + _BATCH_SIZE]
                session.run(
                    "UNWIND $ids AS id CREATE (p:Person {uid: id})",
                    ids=batch,
                )
        logger.info("Memgraph node loading complete.")

    def load_relationships(self, relationships: List[Tuple[int, int]]) -> None:
        logger.info("Loading %d relationships into Memgraph ...", len(relationships))
        with self._driver.session() as session:
            for i in range(0, len(relationships), _BATCH_SIZE):
                batch = [
                    {"src": s, "tgt": t}
                    for s, t in relationships[i : i + _BATCH_SIZE]
                ]
                session.run(
                    """
                    UNWIND $rels AS r
                    MATCH (a:Person {uid: r.src}), (b:Person {uid: r.tgt})
                    CREATE (a)-[:KNOWS]->(b)
                    """,
                    rels=batch,
                )
        logger.info("Memgraph relationship loading complete.")

    def get_node_count(self) -> int:
        with self._driver.session() as session:
            result = session.run("MATCH (n:Person) RETURN count(n) AS cnt")
            return result.single()["cnt"]

    def get_relationship_count(self) -> int:
        with self._driver.session() as session:
            result = session.run("MATCH ()-[r:KNOWS]->() RETURN count(r) AS cnt")
            return result.single()["cnt"]

    # ── Queries ──────────────────────────────────────────────────────────

    def traversal_1hop(self, start_node_id: int) -> List[int]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (a:Person {uid: $uid})-[:KNOWS]->(b) RETURN b.uid AS uid",
                uid=start_node_id,
            )
            return [record["uid"] for record in result]

    def traversal_2hop(self, start_node_id: int) -> List[int]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (a:Person {uid: $uid})-[:KNOWS]->()-[:KNOWS]->(b) "
                "RETURN DISTINCT b.uid AS uid",
                uid=start_node_id,
            )
            return [record["uid"] for record in result]

    def traversal_3hop(self, start_node_id: int) -> List[int]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (a:Person {uid: $uid})-[:KNOWS]->()-[:KNOWS]->()-[:KNOWS]->(b) "
                "RETURN DISTINCT b.uid AS uid",
                uid=start_node_id,
            )
            return [record["uid"] for record in result]

    def point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (p:Person {uid: $uid}) RETURN p.uid AS uid",
                uid=node_id,
            )
            record = result.single()
            return {"uid": record["uid"]} if record else None

    def indexed_lookup(self, min_id: int, max_id: int) -> List[int]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (p:Person) WHERE p.uid >= $min AND p.uid <= $max "
                "RETURN p.uid AS uid",
                min=min_id,
                max=max_id,
            )
            return [record["uid"] for record in result]

    def aggregation_count_by_group(self) -> List[Dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[r:KNOWS]->()
                WITH p, count(r) AS degree
                RETURN degree, count(p) AS node_count
                ORDER BY degree
                """
            )
            return [
                {"degree": record["degree"], "node_count": record["node_count"]}
                for record in result
            ]

    # ── Write operations ─────────────────────────────────────────────────

    def write_create_relationship(self, source_id: int, target_id: int) -> bool:
        try:
            with self._driver.session() as session:
                session.run(
                    "MATCH (a:Person {uid: $src}), (b:Person {uid: $tgt}) "
                    "CREATE (a)-[:KNOWS]->(b)",
                    src=source_id,
                    tgt=target_id,
                )
            return True
        except Neo4jError as e:
            logger.warning("Write failed: %s", e)
            return False

    def write_delete_relationship(self, source_id: int, target_id: int) -> bool:
        try:
            with self._driver.session() as session:
                session.run(
                    "MATCH (a:Person {uid: $src})-[r:KNOWS]->(b:Person {uid: $tgt}) "
                    "DELETE r",
                    src=source_id,
                    tgt=target_id,
                )
            return True
        except Neo4jError as e:
            logger.warning("Delete failed: %s", e)
            return False

    # ── Footprint ────────────────────────────────────────────────────────

    def get_resource_info(self) -> Dict[str, str]:
        info = {
            "platform": "Memgraph",
            "version": "Not observable",
            "instance_type": "Not observable",
            "vcpu": "Not observable",
            "ram": "Not observable",
            "storage": "Not observable",
        }
        try:
            with self._driver.session() as session:
                result = session.run("CALL mg.info()")
                record = result.single()
                if record:
                    info["version"] = str(record.get("version", "Not observable"))
        except Exception:
            pass
        return info
