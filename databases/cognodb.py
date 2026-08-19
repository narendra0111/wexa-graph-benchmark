"""
CognoDB Cloud adapter.

CognoDB exposes a Bolt-compatible endpoint, so we use the official
neo4j Python driver to connect.  Cypher is used as the query language.

Credentials are read from environment variables:
  COGNODB_URI, COGNODB_USERNAME, COGNODB_PASSWORD
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from databases.base import GraphDatabaseAdapter

logger = logging.getLogger("benchmark.cognodb")

# Batch size for bulk loading
_BATCH_SIZE = 500


class CognoDBAdapter(GraphDatabaseAdapter):
    """Adapter for CognoDB Cloud (Bolt + Cypher)."""

    name = "CognoDB"

    def __init__(self) -> None:
        self._driver = None

    # ── Connection ───────────────────────────────────────────────────────

    def connect(self) -> None:
        uri = os.environ["COGNODB_URI"]
        user = os.environ["COGNODB_USERNAME"]
        password = os.environ["COGNODB_PASSWORD"]
        logger.info("Connecting to CognoDB at %s ...", uri)
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        # Verify connectivity
        self._driver.verify_connectivity()
        logger.info("CognoDB connection verified.")

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            logger.info("CognoDB connection closed.")

    # ── Schema / setup ───────────────────────────────────────────────────

    def clear_database(self) -> None:
        logger.info("Clearing CognoDB database ...")
        with self._driver.session() as session:
            # Delete in batches to avoid memory issues
            while True:
                result = session.run(
                    "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) AS deleted"
                )
                deleted = result.single()["deleted"]
                if deleted == 0:
                    break
        logger.info("CognoDB database cleared.")

    def create_indexes(self) -> None:
        """
        Create indexes used by the benchmark queries.

        Indexed properties:
          - Person.uid  (unique node ID — used for point lookups and traversals)
        """
        logger.info("Creating CognoDB indexes ...")
        with self._driver.session() as session:
            session.run(
                "CREATE INDEX person_uid_index IF NOT EXISTS "
                "FOR (p:Person) ON (p.uid)"
            )
        logger.info("CognoDB indexes created.")

    # ── Data loading ─────────────────────────────────────────────────────

    def load_nodes(self, node_ids: List[int]) -> None:
        logger.info("Loading %d nodes into CognoDB ...", len(node_ids))
        with self._driver.session() as session:
            for i in range(0, len(node_ids), _BATCH_SIZE):
                batch = node_ids[i : i + _BATCH_SIZE]
                session.run(
                    "UNWIND $ids AS id CREATE (p:Person {uid: id})",
                    ids=batch,
                )
        logger.info("CognoDB node loading complete.")

    def load_relationships(self, relationships: List[Tuple[int, int]]) -> None:
        logger.info("Loading %d relationships into CognoDB ...", len(relationships))
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
        logger.info("CognoDB relationship loading complete.")

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
                "MATCH (a:Person {uid: $uid})-[:KNOWS*2]->(b) "
                "RETURN DISTINCT b.uid AS uid",
                uid=start_node_id,
            )
            return [record["uid"] for record in result]

    def traversal_3hop(self, start_node_id: int) -> List[int]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (a:Person {uid: $uid})-[:KNOWS*3]->(b) "
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
            "platform": "CognoDB Cloud",
            "version": "Not observable",
            "instance_type": "Not observable",
            "vcpu": "Not observable",
            "ram": "Not observable",
            "storage": "Not observable",
        }
        try:
            with self._driver.session() as session:
                result = session.run("CALL dbms.components()")
                for record in result:
                    info["version"] = str(record.get("versions", "Not observable"))
        except Exception:
            pass
        return info
