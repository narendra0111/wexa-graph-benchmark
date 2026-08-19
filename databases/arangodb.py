"""
ArangoDB adapter.

ArangoDB is a multi-model database that supports graph operations
through AQL (ArangoDB Query Language).  It uses collections for
vertices and edges rather than labels and relationships.

Credentials: ARANGODB_HOST, ARANGODB_USERNAME, ARANGODB_PASSWORD, ARANGODB_DATABASE
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from arango import ArangoClient
from arango.exceptions import (
    CollectionCreateError,
    DocumentInsertError,
    GraphCreateError,
    IndexCreateError,
)

from databases.base import GraphDatabaseAdapter

logger = logging.getLogger("benchmark.arangodb")

_BATCH_SIZE = 500
_VERTEX_COLLECTION = "persons"
_EDGE_COLLECTION = "knows"
_GRAPH_NAME = "social"


class ArangoDBAdapter(GraphDatabaseAdapter):
    """Adapter for ArangoDB (ArangoGraph Insights or self-hosted)."""

    name = "ArangoDB"

    def __init__(self) -> None:
        self._client = None
        self._db = None
        self._graph = None

    # ── Connection ───────────────────────────────────────────────────────

    def connect(self) -> None:
        host = os.environ["ARANGODB_HOST"]
        user = os.environ.get("ARANGODB_USERNAME", "root")
        password = os.environ.get("ARANGODB_PASSWORD", "")
        db_name = os.environ.get("ARANGODB_DATABASE", "graph_benchmark")

        logger.info("Connecting to ArangoDB at %s ...", host)
        self._client = ArangoClient(hosts=host)
        self._db = self._client.db(db_name, username=user, password=password)
        # Verify connectivity
        self._db.version()
        logger.info("ArangoDB connection verified (db=%s).", db_name)

    def close(self) -> None:
        # python-arango doesn't have an explicit close
        logger.info("ArangoDB connection closed (no-op).")

    # ── Schema / setup ───────────────────────────────────────────────────

    def clear_database(self) -> None:
        logger.info("Clearing ArangoDB collections ...")
        if self._db.has_graph(_GRAPH_NAME):
            self._db.delete_graph(_GRAPH_NAME, drop_collections=True)
        for name in [_VERTEX_COLLECTION, _EDGE_COLLECTION]:
            if self._db.has_collection(name):
                self._db.delete_collection(name)
        # Re-create
        try:
            self._db.create_collection(_VERTEX_COLLECTION)
        except CollectionCreateError:
            pass
        try:
            self._db.create_collection(_EDGE_COLLECTION, edge=True)
        except CollectionCreateError:
            pass
        try:
            self._db.create_graph(
                _GRAPH_NAME,
                edge_definitions=[
                    {
                        "edge_collection": _EDGE_COLLECTION,
                        "from_vertex_collections": [_VERTEX_COLLECTION],
                        "to_vertex_collections": [_VERTEX_COLLECTION],
                    }
                ],
            )
        except GraphCreateError:
            pass
        self._graph = self._db.graph(_GRAPH_NAME)
        logger.info("ArangoDB cleared and graph re-created.")

    def create_indexes(self) -> None:
        """Indexed property: persons.uid (persistent index)"""
        logger.info("Creating ArangoDB indexes ...")
        col = self._db.collection(_VERTEX_COLLECTION)
        try:
            col.add_persistent_index(fields=["uid"], unique=False)
        except IndexCreateError:
            pass
        logger.info("ArangoDB indexes created.")

    # ── Data loading ─────────────────────────────────────────────────────

    def load_nodes(self, node_ids: List[int]) -> None:
        logger.info("Loading %d nodes into ArangoDB ...", len(node_ids))
        col = self._db.collection(_VERTEX_COLLECTION)
        for i in range(0, len(node_ids), _BATCH_SIZE):
            batch = [
                {"_key": str(nid), "uid": nid}
                for nid in node_ids[i : i + _BATCH_SIZE]
            ]
            try:
                col.insert_many(batch, overwrite=True, silent=True)
            except DocumentInsertError as e:
                logger.warning("Batch insert error: %s", e)
        logger.info("ArangoDB node loading complete.")

    def load_relationships(self, relationships: List[Tuple[int, int]]) -> None:
        logger.info("Loading %d relationships into ArangoDB ...", len(relationships))
        col = self._db.collection(_EDGE_COLLECTION)
        for i in range(0, len(relationships), _BATCH_SIZE):
            batch = [
                {
                    "_from": f"{_VERTEX_COLLECTION}/{s}",
                    "_to": f"{_VERTEX_COLLECTION}/{t}",
                }
                for s, t in relationships[i : i + _BATCH_SIZE]
            ]
            try:
                col.insert_many(batch, silent=True)
            except DocumentInsertError as e:
                logger.warning("Batch insert error: %s", e)
        logger.info("ArangoDB relationship loading complete.")

    def get_node_count(self) -> int:
        return self._db.collection(_VERTEX_COLLECTION).count()

    def get_relationship_count(self) -> int:
        return self._db.collection(_EDGE_COLLECTION).count()

    # ── Queries ──────────────────────────────────────────────────────────

    def traversal_1hop(self, start_node_id: int) -> List[int]:
        cursor = self._db.aql.execute(
            """
            FOR v IN 1..1 OUTBOUND @start GRAPH @graph
              RETURN v.uid
            """,
            bind_vars={
                "start": f"{_VERTEX_COLLECTION}/{start_node_id}",
                "graph": _GRAPH_NAME,
            },
        )
        return list(cursor)

    def traversal_2hop(self, start_node_id: int) -> List[int]:
        cursor = self._db.aql.execute(
            """
            FOR v IN 2..2 OUTBOUND @start GRAPH @graph
              RETURN DISTINCT v.uid
            """,
            bind_vars={
                "start": f"{_VERTEX_COLLECTION}/{start_node_id}",
                "graph": _GRAPH_NAME,
            },
        )
        return list(cursor)

    def traversal_3hop(self, start_node_id: int) -> List[int]:
        cursor = self._db.aql.execute(
            """
            FOR v IN 3..3 OUTBOUND @start GRAPH @graph
              RETURN DISTINCT v.uid
            """,
            bind_vars={
                "start": f"{_VERTEX_COLLECTION}/{start_node_id}",
                "graph": _GRAPH_NAME,
            },
        )
        return list(cursor)

    def point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        cursor = self._db.aql.execute(
            "FOR p IN @@col FILTER p.uid == @uid RETURN p.uid",
            bind_vars={"@col": _VERTEX_COLLECTION, "uid": node_id},
        )
        results = list(cursor)
        return {"uid": results[0]} if results else None

    def indexed_lookup(self, min_id: int, max_id: int) -> List[int]:
        cursor = self._db.aql.execute(
            """
            FOR p IN @@col
              FILTER p.uid >= @min AND p.uid <= @max
              RETURN p.uid
            """,
            bind_vars={
                "@col": _VERTEX_COLLECTION,
                "min": min_id,
                "max": max_id,
            },
        )
        return list(cursor)

    def aggregation_count_by_group(self) -> List[Dict[str, Any]]:
        cursor = self._db.aql.execute(
            """
            FOR p IN @@vcol
              LET degree = LENGTH(
                FOR e IN @@ecol FILTER e._from == CONCAT(@prefix, "/", TO_STRING(p.uid)) RETURN 1
              )
              COLLECT deg = degree WITH COUNT INTO node_count
              SORT deg
              RETURN {degree: deg, node_count: node_count}
            """,
            bind_vars={
                "@vcol": _VERTEX_COLLECTION,
                "@ecol": _EDGE_COLLECTION,
                "prefix": _VERTEX_COLLECTION,
            },
        )
        return list(cursor)

    # ── Write operations ─────────────────────────────────────────────────

    def write_create_relationship(self, source_id: int, target_id: int) -> bool:
        try:
            col = self._db.collection(_EDGE_COLLECTION)
            col.insert(
                {
                    "_from": f"{_VERTEX_COLLECTION}/{source_id}",
                    "_to": f"{_VERTEX_COLLECTION}/{target_id}",
                },
                silent=True,
            )
            return True
        except Exception as e:
            logger.warning("Write failed: %s", e)
            return False

    def write_delete_relationship(self, source_id: int, target_id: int) -> bool:
        try:
            cursor = self._db.aql.execute(
                """
                FOR e IN @@col
                  FILTER e._from == @src AND e._to == @tgt
                  LIMIT 1
                  REMOVE e IN @@col
                  RETURN OLD
                """,
                bind_vars={
                    "@col": _EDGE_COLLECTION,
                    "src": f"{_VERTEX_COLLECTION}/{source_id}",
                    "tgt": f"{_VERTEX_COLLECTION}/{target_id}",
                },
            )
            return len(list(cursor)) > 0
        except Exception as e:
            logger.warning("Delete failed: %s", e)
            return False

    # ── Footprint ────────────────────────────────────────────────────────

    def get_resource_info(self) -> Dict[str, str]:
        info = {
            "platform": "ArangoDB",
            "version": "Not observable",
            "instance_type": "Not observable",
            "vcpu": "Not observable",
            "ram": "Not observable",
            "storage": "Not observable",
        }
        try:
            info["version"] = self._db.version()
        except Exception:
            pass
        return info
