"""
Abstract base class that every database adapter must implement.

This guarantees a uniform API so the benchmark runner is completely
database-agnostic.  Each adapter translates these operations into the
database's native query language / driver calls.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class GraphDatabaseAdapter(ABC):
    """Common interface for all graph database adapters."""

    # Human-readable name used in results and charts
    name: str = "BaseAdapter"

    # ── Connection lifecycle ─────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the database."""

    @abstractmethod
    def close(self) -> None:
        """Cleanly close the database connection."""

    # ── Schema / setup ───────────────────────────────────────────────────

    @abstractmethod
    def clear_database(self) -> None:
        """Delete all nodes and relationships (used before data loading)."""

    @abstractmethod
    def create_indexes(self) -> None:
        """Create indexes required by the benchmark queries."""

    # ── Data loading ─────────────────────────────────────────────────────

    @abstractmethod
    def load_nodes(self, node_ids: List[int]) -> None:
        """Bulk-create nodes with the given integer IDs."""

    @abstractmethod
    def load_relationships(
        self, relationships: List[Tuple[int, int]]
    ) -> None:
        """Bulk-create directed KNOWS relationships (source → target)."""

    @abstractmethod
    def get_node_count(self) -> int:
        """Return the total number of nodes in the database."""

    @abstractmethod
    def get_relationship_count(self) -> int:
        """Return the total number of relationships in the database."""

    # ── Queries (used by benchmark workloads) ────────────────────────────

    @abstractmethod
    def traversal_1hop(self, start_node_id: int) -> List[int]:
        """Return IDs of nodes exactly 1 hop from *start_node_id*."""

    @abstractmethod
    def traversal_2hop(self, start_node_id: int) -> List[int]:
        """Return IDs of nodes exactly 2 hops from *start_node_id*."""

    @abstractmethod
    def traversal_3hop(self, start_node_id: int) -> List[int]:
        """Return IDs of nodes exactly 3 hops from *start_node_id*."""

    @abstractmethod
    def point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        """Look up a single node by its unique ID property."""

    @abstractmethod
    def indexed_lookup(self, min_id: int, max_id: int) -> List[int]:
        """Return node IDs where the indexed property falls in [min_id, max_id]."""

    @abstractmethod
    def aggregation_count_by_group(self) -> List[Dict[str, Any]]:
        """
        Run a count / group-by query.

        For the Pokec dataset we group nodes by the number of outgoing
        relationships (degree distribution) and return each group with its
        count.
        """

    # ── Write operations (used by mixed workload) ────────────────────────

    @abstractmethod
    def write_create_relationship(
        self, source_id: int, target_id: int
    ) -> bool:
        """Create a single KNOWS relationship.  Return True on success."""

    @abstractmethod
    def write_delete_relationship(
        self, source_id: int, target_id: int
    ) -> bool:
        """Delete a single KNOWS relationship.  Return True on success."""

    # ── Footprint / resource info ────────────────────────────────────────

    @abstractmethod
    def get_resource_info(self) -> Dict[str, str]:
        """
        Return observable resource / instance information.

        Keys may include: instance_type, vcpu, ram, storage, version.
        Use "Not observable" for anything the platform does not expose.
        """

    # ── Convenience ──────────────────────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
