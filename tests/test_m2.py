from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.adapter_demo import SupportedReadAdapter
from memory_lifecycle_bench.__main__ import main
from memory_lifecycle_bench.agent import POLICIES, SHORT_WINDOW_SECONDS, TenantMemoryTools, select
from memory_lifecycle_bench.api import run_file
from memory_lifecycle_bench.faults import FAULTS, ExpiredGetFault, fault_input_bytes, run_fault_demo
from memory_lifecycle_bench.model import Memory
from memory_lifecycle_bench.runner import compare, evaluate
from memory_lifecycle_bench.scoring import LifecycleLedger
from memory_lifecycle_bench.store import SQLiteStore
from memory_lifecycle_bench.suite import Probe, load_suite

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "examples/lifecycle-v1.json"


class M2PolicyAndReopenTests(unittest.TestCase):
    def test_full_fixture_has_exact_category_counts_and_paired_controls(self):
        suite = load_suite(FULL)
        self.assertEqual(Counter(s.category for s in suite.scenarios),
                         {"retention": 2, "expiration": 3, "deletion": 3, "tenant": 2, "stale": 3, "conflict": 3})
        for scenario in suite.scenarios:
            for index, event in enumerate(scenario.events):
                if isinstance(event, Probe) and event.reason in ("expired", "deleted"):
                    positives = [p for p in scenario.events[:index] if isinstance(p, Probe)
                                 and p.path == event.path and p.tenant_id == event.tenant_id
                                 and p.inputs == event.inputs and p.reason == "present" and p.expected_ids]
                    self.assertTrue(positives, f"missing paired positive for {scenario.scenario_id}/{event.probe_id}")

    def test_short_window_exact_boundary_applies_to_search_and_get(self):
        store = SQLiteStore()
        self.addCleanup(store.close)
        record = Memory("tenant-a", "old-fact", "fictional-person", "channel", "email", 0, 0, None, "fictional")
        store.put(record)
        before = TenantMemoryTools(store, "tenant-a", SHORT_WINDOW_SECONDS - 1, max_age_seconds=SHORT_WINDOW_SECONDS)
        self.assertEqual(before.search(record.subject, record.key), (record,))
        self.assertEqual(before.get(record.memory_id), record)
        boundary = TenantMemoryTools(store, "tenant-a", SHORT_WINDOW_SECONDS, max_age_seconds=SHORT_WINDOW_SECONDS)
        self.assertEqual(boundary.search(record.subject, record.key), ())
        self.assertIsNone(boundary.get(record.memory_id))
        self.assertTrue(all(o.excluded_by_retention == ("old-fact",) and o.memories == (record,)
                            for o in boundary.observations))

    def test_retention_cannot_hide_raw_adapter_lifecycle_violation(self):
        store = ExpiredGetFault(":memory:")
        self.addCleanup(store.close)
        record = Memory("northwind", "fixed-trial", "fictional-trial", "queue", "trial-support", 0, 0, 10, "fictional")
        store.put(record)
        tools = TenantMemoryTools(store, "northwind", 100, max_age_seconds=1)
        self.assertIsNone(tools.get("fixed-trial"))
        ledger = LifecycleLedger()
        ledger.put(record)
        self.assertEqual(tools.observations[0].excluded_by_retention, ("fixed-trial",))
        self.assertIn("expired", [v["kind"] for v in ledger.inspect(tools.observations[0])])

    def test_valid_time_tie_break_is_id_not_late_recorded_time(self):
        a = Memory("tenant-a", "a", "fictional-person", "channel", "email", 20, 0, None, "fictional")
        b = Memory("tenant-a", "b", "fictional-person", "channel", "voice", 0, 0, None, "fictional")
        self.assertEqual(select((a, b), "last-write").value, "email")
        self.assertEqual(select((a, b), "valid-time").value, "voice")
        self.assertEqual(select((a, b), "conservative").status, "conflict")

    def test_conservative_full_run_and_actual_close_reopen_preserve_state(self):
        instances, paths = [], []

        class TrackingStore(SQLiteStore):
            def __init__(self, path):
                super().__init__(path)
                self.was_closed = False
                paths.append(path)
                instances.append(self)

            def close(self):
                super().close()
                self.was_closed = True

        report, traces = evaluate(load_suite(FULL), "conservative", TrackingStore)
        self.assertTrue(report["passed"])
        self.assertEqual(report["summary"]["tasks"], {"passed": 36, "total": 36})
        self.assertEqual(report["summary"]["positive_answers"], {"passed": 28, "total": 28})
        self.assertEqual(report["summary"]["required_abstentions"], {"passed": 8, "total": 8})
        self.assertEqual(report["summary"]["reopens"], 2)
        self.assertEqual(len([r for r in traces if r["type"] == "reopen"]), 2)
        self.assertEqual(len(instances), 18)
        self.assertTrue(all(s.was_closed for s in instances))
        self.assertEqual(len(set(paths)), 16)
        self.assertTrue(all(p.name.startswith("scenario-") and not p.exists() for p in paths))

    def test_baseline_failures_are_preserved_in_comparison(self):
        before = FULL.read_bytes()
        with TemporaryDirectory() as directory:
            result = compare(load_suite(FULL), directory)
            self.assertTrue(result["completed"])
            self.assertFalse(result["passed"])
            self.assertEqual([r["policy"] for r in result["configurations"]], list(POLICIES))
            reports = {p: json.loads((Path(directory) / p / "report.json").read_text(encoding="utf-8")) for p in POLICIES}
            self.assertTrue(reports["conservative"]["passed"])
            self.assertTrue(all(not reports[p]["passed"] for p in POLICIES if p != "conservative"))
            self.assertTrue(all(r["summary"]["contract_violations"] == 0 for r in reports.values()))
            checks = {(c["scenario"], c["id"]): c for c in reports["last-write"]["checks"]}
            late = checks[("late-arriving-historical-fact", "after-history")]
            self.assertFalse(late["passed"])
            self.assertEqual(late["observed"]["value"], "voice")
            self.assertEqual(reports["last-write"]["summary"]["stale_answers"], 1)
            self.assertEqual(reports["valid-time"]["summary"]["confident_conflict_errors"], 2)
            self.assertEqual(reports["short-window"]["summary"]["retention_task_losses"], 2)
            self.assertEqual({r["suite_sha256"] for r in reports.values()}, {load_suite(FULL).digest})
        self.assertEqual(FULL.read_bytes(), before)

    def test_public_adapter_api_uses_supported_reads_and_private_factory_path(self):
        constructor_paths, read_fields = [], []

        class InspectableAdapter(SupportedReadAdapter):
            def __init__(self, path):
                self.assert_path = path
                constructor_paths.append(path.name)
                super().__init__(path)

            def search(self, tenant_id, subject, key, at):
                read_fields.append((tenant_id, subject, key, at))
                return super().search(tenant_id, subject, key, at)

            def get(self, tenant_id, memory_id, at):
                read_fields.append((tenant_id, memory_id, at))
                return super().get(tenant_id, memory_id, at)

        with TemporaryDirectory() as directory:
            report = run_file(FULL, directory, store_factory=InspectableAdapter)
            self.assertTrue(report["passed"])
        self.assertTrue(all(name.startswith("scenario-") for name in constructor_paths))
        self.assertTrue(read_fields)
        self.assertTrue(all(len(row) in (3, 4) and isinstance(row[-1], int) for row in read_fields))


class M2FaultCliTests(unittest.TestCase):
    def test_all_fixed_faults_fail_with_named_violations_and_unchanged_inputs(self):
        for fault, path, kind in (("expired-get", "get", "expired"),
                                 ("deleted-search", "search", "deleted"),
                                 ("tenant-search", "search", "tenant")):
            with self.subTest(fault=fault), TemporaryDirectory() as directory:
                raw = fault_input_bytes(fault)
                report = run_fault_demo(fault, directory)
                reference = json.loads((Path(directory) / "reference/report.json").read_text(encoding="utf-8"))
                self.assertTrue(reference["passed"])
                self.assertFalse(report["passed"])
                self.assertGreater(report["supported_paths"][path]["violations"][kind], 0)
                self.assertTrue(report["fault_demo"]["diagnostic_valid"])
                self.assertTrue(report["fault_demo"]["positive_controls_preserved"])
                self.assertTrue(report["fault_demo"]["input_bytes_unchanged"])
                self.assertEqual((Path(directory) / "input.json").read_bytes(), raw)
                self.assertEqual(fault_input_bytes(fault), raw)
                self.assertEqual(reference["suite_sha256"], report["suite_sha256"])
                self.assertEqual(report["suite_sha256"], sha256(raw).hexdigest())

    def test_fault_cli_exit_is_one_and_has_no_production_input_switch(self):
        before = FULL.read_bytes()
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            for fault in FAULTS:
                self.assertEqual(main(["fault-demo", "--fault", fault, "--out", directory]), 1)
            for args in (["fault-demo", str(FULL), "--fault", "expired-get", "--out", directory],
                         ["run", str(FULL), "--fault", "expired-get", "--out", directory]):
                with self.assertRaises(SystemExit) as raised:
                    main(args)
                self.assertEqual(raised.exception.code, 2)
        self.assertEqual(FULL.read_bytes(), before)

    def test_fault_diagnostic_cannot_claim_valid_when_positive_controls_fail(self):
        with TemporaryDirectory() as directory:
            with patch("memory_lifecycle_bench.faults.TenantSearchFault.search", side_effect=RuntimeError("broken control")):
                report = run_fault_demo("tenant-search", directory)
            self.assertFalse(report["fault_demo"]["positive_controls_preserved"])
            self.assertFalse(report["fault_demo"]["diagnostic_valid"])
            self.assertFalse(report["passed"])

    def test_comparison_completion_exit_and_strict_failure_are_distinct(self):
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()) as output:
            self.assertEqual(main(["compare", str(FULL), "--out", directory]), 0)
            self.assertIn("overall_passed=false", output.getvalue())
            self.assertEqual(main(["compare", str(FULL), "--out", directory, "--strict"]), 1)


if __name__ == "__main__":
    unittest.main()
