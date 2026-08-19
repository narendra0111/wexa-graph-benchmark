#!/usr/bin/env python3
"""
Connectivity test for all configured database adapters.

Run:  python tests/test_connectivity.py

Tests each enabled database:
  1. Connect
  2. Authenticate
  3. Run a simple query
  4. Create and read a test node
  5. Clean up
  6. Disconnect

Usage:
  python tests/test_connectivity.py              # test all enabled databases
  python tests/test_connectivity.py cognodb       # test only CognoDB
"""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from dotenv import load_dotenv

from config import BenchmarkConfig

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_connectivity")


def get_adapter(db_name: str):
    """Dynamically import and return the adapter class for a database."""
    if db_name == "cognodb":
        from databases.cognodb import CognoDBAdapter
        return CognoDBAdapter()
    elif db_name == "neo4j":
        from databases.neo4j_adapter import Neo4jAdapter
        return Neo4jAdapter()
    elif db_name == "memgraph":
        from databases.memgraph import MemgraphAdapter
        return MemgraphAdapter()
    elif db_name == "falkordb":
        from databases.falkordb import FalkorDBAdapter
        return FalkorDBAdapter()
    elif db_name == "arangodb":
        from databases.arangodb import ArangoDBAdapter
        return ArangoDBAdapter()
    else:
        raise ValueError(f"Unknown database: {db_name}")


def test_database(db_name: str) -> bool:
    """
    Test connectivity for a single database.

    Returns True if all checks pass, False otherwise.
    """
    print(f"\n{'─' * 50}")
    print(f"  Testing: {db_name}")
    print(f"{'─' * 50}")

    try:
        adapter = get_adapter(db_name)

        # Step 1: Connect
        print("  [1/5] Connecting ...", end=" ")
        adapter.connect()
        print("✓")

        # Step 2: Clear (verifies write access)
        print("  [2/5] Clearing database ...", end=" ")
        adapter.clear_database()
        print("✓")

        # Step 3: Create indexes
        print("  [3/5] Creating indexes ...", end=" ")
        adapter.create_indexes()
        print("✓")

        # Step 4: Create and read a test node
        print("  [4/5] Creating test node ...", end=" ")
        adapter.load_nodes([999999])
        result = adapter.point_lookup(999999)
        assert result is not None, "Test node not found after creation"
        print("✓")

        # Step 5: Clean up and close
        print("  [5/5] Cleaning up ...", end=" ")
        adapter.clear_database()
        adapter.close()
        print("✓")

        print(f"\n  ✅ {db_name}: ALL CHECKS PASSED")
        return True

    except Exception as e:
        print(f"\n  ❌ {db_name}: FAILED — {e}")
        logger.exception("Connectivity test failed for %s", db_name)
        return False


def main():
    config = BenchmarkConfig()

    # Allow testing a single database via command-line argument
    if len(sys.argv) > 1:
        databases = [sys.argv[1]]
    else:
        databases = config.enabled_databases

    print("=" * 50)
    print("  Database Connectivity Tests")
    print("=" * 50)

    results = {}
    for db in databases:
        results[db] = test_database(db)

    # Summary
    print(f"\n{'=' * 50}")
    print("  Summary")
    print(f"{'=' * 50}")
    for db, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {db:15s} {status}")

    all_passed = all(results.values())
    print()
    if all_passed:
        print("  All databases passed connectivity tests.")
    else:
        failed = [db for db, passed in results.items() if not passed]
        print(f"  WARNING: {len(failed)} database(s) failed: {', '.join(failed)}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
