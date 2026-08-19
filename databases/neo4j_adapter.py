"""
Neo4j adapter (Aura or self-hosted).

Uses the official neo4j Python driver and Cypher queries — identical
query logic to CognoDB since both speak Cypher over Bolt.

Credentials: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from databases.base import GraphDatabaseAdapter

logger = logging.getLogger("benchmark.neo4j")

_BATCH_SIZE = 500


class Neo4jAdapter(GraphDatabaseAdapter):
    """Adapter for Neo4j (Aura Free or self-hosted)."""

    name = "Neo4j"

    def __init__(self) -> None:
        self._driver = None

    # ── Connection ───────────────────────────────────────────────────────

    def connect(self) -> None:
        uri = os.environ["NEO4J_URI"]
        user = os.environ["NEO4J_USERNAME"]
        password = os.environ["NEO4J_PASSWORD"]
        logger.info("Connecting to Neo4j at %s ...", uri)
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._driver.verify_connectivity()
        logger.info("Neo4j connection verified.")

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed.")

    # ── Schema / setup ───────────────────────────────────────────────────

    def clear_database(self) -> None:
        logger.info("Clearing Neo4j database ...")
        with self._driver.session() as session:
            while True:
                result = session.run(
                    "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) AS deleted"
                )
                deleted = result.single()["deleted"]
                if deleted == 0:
                    break
        logger.info("Neo4j database cleared.")

    def create_indexes(self) -> None:
        """Indexed property: Person.uid"""
        logger.info("Creating Neo4j indexes ...")
        with self._driver.session() as session:
            session.run(
                "CREATE INDEX person_uid_index IF NOT EXISTS "
                "FOR (p:Person) ON (p.uid)"
            )
        logger.info("Neo4j indexes created.")

    # ── Data loading ─────────────────────────────────────────────────────

    def load_nodes(self, node_ids: List[int]) -> None:
        logger.info("Loading %d nodes into Neo4j ...", len(node_ids))
        with self._driver.session() as session:
            for i in range(0, len(node_ids), _BATCH_SIZE):
                batch = node_ids[i : i + _BATCH_SIZE]
                session.run(
                    "UNWIND $ids AS id CREATE (p:Person {uid: id})",
                    ids=batch,
                )
        logger.info("Neo4j node loading complete.")

    def load_relationships(self, relationships: List[Tuple[int, int]]) -> None:
        logger.info("Loading %d relationships into Neo4j ...", len(relationships))
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
        logger.info("Neo4j relationship loading complete.")

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
            "platform": "Neo4j Aura",
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
