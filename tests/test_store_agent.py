from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from memory_lifecycle_bench.agent import TenantMemoryTools, ToolExecutionError, answer, select
from memory_lifecycle_bench.model import Memory, Query, ValidationError, VirtualClock
from memory_lifecycle_bench.store import SQLiteStore


def memory(**changes):
    base = Memory("tenant-a", "fact-a", "fictional-person", "channel", "email", 0, 0, None, "fictional test")
    return replace(base, **changes)


class StoreSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.store = SQLiteStore()
        self.addCleanup(self.store.close)

    def test_expiry_before_exact_boundary_and_after_on_both_paths(self):
        record = memory(expires_at=10)
        self.store.put(record)
        self.assertEqual(self.store.search("tenant-a", record.subject, record.key, 9), (record,))
        self.assertEqual(self.store.get("tenant-a", record.memory_id, 9), record)
        for at in (10, 11, 100):
            with self.subTest(at=at):
                self.assertEqual(self.store.search("tenant-a", record.subject, record.key, at), ())
                self.assertIsNone(self.store.get("tenant-a", record.memory_id, at))

    def test_delete_after_warmed_reads_removes_both_supported_paths(self):
        record = memory()
        self.store.put(record)
        self.assertEqual(self.store.get("tenant-a", "fact-a", 0), record)
        self.assertEqual(self.store.search("tenant-a", record.subject, record.key, 0), (record,))
        self.assertTrue(self.store.delete("tenant-a", "fact-a"))
        self.assertFalse(self.store.delete("tenant-a", "fact-a"))
        self.assertIsNone(self.store.get("tenant-a", "fact-a", 0))
        self.assertEqual(self.store.search("tenant-a", record.subject, record.key, 0), ())

    def test_shared_id_is_tenant_scoped_and_delete_does_not_cross_scope(self):
        north, south = memory(), memory(tenant_id="tenant-b", value="voice")
        self.store.put(north)
        self.store.put(south)
        self.assertEqual(self.store.get("tenant-a", "fact-a", 1).value, "email")
        self.assertEqual(self.store.get("tenant-b", "fact-a", 1).value, "voice")
        self.assertEqual(self.store.search("tenant-b", south.subject, south.key, 1), (south,))
        self.assertIsNone(self.store.get("tenant-c", "fact-a", 1))
        self.assertEqual(self.store.search("tenant-c", north.subject, north.key, 1), ())
        self.assertFalse(self.store.delete("tenant-c", "fact-a"))
        self.store.delete("tenant-a", "fact-a")
        self.assertIsNone(self.store.get("tenant-a", "fact-a", 1))
        self.assertEqual(self.store.get("tenant-b", "fact-a", 1), south)

    def test_idempotent_replay_cannot_resurrect_deleted_identity(self):
        record = memory()
        self.assertTrue(self.store.put(record))
        self.assertFalse(self.store.put(record))
        self.store.delete("tenant-a", "fact-a")
        self.assertFalse(self.store.put(record))
        self.assertIsNone(self.store.get("tenant-a", "fact-a", 2))
        self.assertEqual(self.store.search("tenant-a", record.subject, record.key, 2), ())
        with self.assertRaises(ValidationError):
            self.store.put(replace(record, value="changed"))

    def test_future_effective_record_is_hidden_until_effective_time(self):
        record = memory(effective_at=5, expires_at=10)
        self.store.put(record)
        self.assertIsNone(self.store.get("tenant-a", "fact-a", 4))
        self.assertEqual(self.store.search("tenant-a", record.subject, record.key, 4), ())
        self.assertEqual(self.store.get("tenant-a", "fact-a", 5), record)

    def test_unbounded_retention_and_quoted_value(self):
        record = memory(value="fictional 'quoted'; DROP TABLE memories; --")
        self.store.put(record)
        self.assertEqual(self.store.get("tenant-a", "fact-a", 2592000), record)
        self.assertEqual(self.store.search("tenant-a", record.subject, record.key, 2592000), (record,))

    def test_empty_tenant_and_invalid_clock_are_rejected(self):
        for operation in (
            lambda: self.store.get("", "fact-a", 0),
            lambda: self.store.search("", "fictional-person", "channel", 0),
            lambda: self.store.delete("", "fact-a"),
            lambda: self.store.put(memory(tenant_id="")),
            lambda: self.store.get("tenant-a", "fact-a", True),
        ):
            with self.subTest(operation=operation), self.assertRaises(ValidationError):
                operation()

    def test_tombstone_and_expiration_survive_database_reopen(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.sqlite"
            store = SQLiteStore(path)
            store.put(memory())
            store.put(memory(memory_id="expiring", expires_at=10))
            store.delete("tenant-a", "fact-a")
            store.close()
            reopened = SQLiteStore(path)
            try:
                self.assertIsNone(reopened.get("tenant-a", "fact-a", 10))
                self.assertIsNone(reopened.get("tenant-a", "expiring", 10))
                self.assertEqual(reopened.search("tenant-a", "fictional-person", "channel", 10), ())
            finally:
                reopened.close()


class MockPolicyTests(unittest.TestCase):
    def test_late_historical_record_exposes_last_write_tradeoff(self):
        current = memory(memory_id="current", recorded_at=10, effective_at=10, value="email")
        historical = memory(memory_id="historical", recorded_at=20, effective_at=0, value="voice")
        records = (current, historical)
        self.assertEqual(select(records, "last-write").value, "voice")
        self.assertEqual(select(records, "conservative").value, "email")

    def test_conservative_conflicts_and_agreeing_claims(self):
        a = memory(memory_id="a", value="email")
        b = memory(memory_id="b", value="voice")
        result = select((b, a), "conservative")
        self.assertEqual((result.status, result.value, result.evidence_ids), ("conflict", None, ("a", "b")))
        self.assertEqual(select((a, replace(b, value="email")), "conservative").evidence_ids, ("b",))
        self.assertEqual(select((), "conservative").status, "unknown")

    def test_mock_uses_search_then_get_with_bounded_tools(self):
        store = SQLiteStore()
        self.addCleanup(store.close)
        store.put(memory())
        tools = TenantMemoryTools(store, "tenant-a", 0)
        result = answer(Query("fictional-person", "channel", "Which fictional channel applies?"), tools, "conservative")
        self.assertEqual((result.status, result.value, result.evidence_ids), ("answer", "email", ("fact-a",)))
        self.assertEqual([o.path for o in tools.observations], ["search", "get"])
        with self.assertRaises(ToolExecutionError):
            tools.get("fact-a")

    def test_clock_cannot_move_backwards(self):
        clock = VirtualClock()
        clock.advance(10)
        clock.advance(10)
        with self.assertRaises(ValidationError):
            clock.advance(9)


if __name__ == "__main__":
    unittest.main()
