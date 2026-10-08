from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import fields
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from memory_lifecycle_bench.__main__ import main
from memory_lifecycle_bench.agent import answer as real_answer
from memory_lifecycle_bench.model import Memory, Query, ReadObservation, ValidationError
from memory_lifecycle_bench.runner import evaluate, write_reports
from memory_lifecycle_bench.store import SQLiteStore
from memory_lifecycle_bench.scoring import LifecycleLedger
from memory_lifecycle_bench.suite import MAX_BYTES, load_suite, parse_suite

SMOKE = Path(__file__).resolve().parents[1] / "examples" / "smoke-v1.json"


class EmptyStore(SQLiteStore):
    """Negative control: safe absence everywhere but cannot do useful tasks."""
    def search(self, tenant_id, subject, key, at):
        return ()

    def get(self, tenant_id, memory_id, at):
        return None


class ExpiredGetStore(SQLiteStore):
    """Deliberate test defect: ID reads ignore current virtual time."""
    def get(self, tenant_id, memory_id, at):
        return super().get(tenant_id, memory_id, 0)


class DeletedGetStore(SQLiteStore):
    """Deliberate test defect: a deleted record escapes through stale ID cache."""
    def __init__(self, path):
        super().__init__(path)
        self.deleted_cache = {}

    def delete(self, tenant_id, memory_id):
        before = super().get(tenant_id, memory_id, 0)
        changed = super().delete(tenant_id, memory_id)
        if changed and before:
            self.deleted_cache[(tenant_id, memory_id)] = before
        return changed

    def get(self, tenant_id, memory_id, at):
        return super().get(tenant_id, memory_id, at) or self.deleted_cache.get((tenant_id, memory_id))


class ForeignSearchStore(SQLiteStore):
    """Deliberate test defect: one subject's search omits the bound tenant."""
    def search(self, tenant_id, subject, key, at):
        tenant = "northwind" if subject == "fictional-ava" else tenant_id
        return super().search(tenant, subject, key, at)


class FailingReadStore(SQLiteStore):
    def search(self, tenant_id, subject, key, at):
        raise RuntimeError("injected fictional backend failure")


class SuiteValidationTests(unittest.TestCase):
    def document(self):
        return json.loads(SMOKE.read_text(encoding="utf-8"))

    def test_four_scenario_fixture_and_fingerprint(self):
        first, second = load_suite(SMOKE), load_suite(SMOKE)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(len(first.digest), 64)
        self.assertEqual(len(first.scenarios), 4)
        self.assertEqual({s.category for s in first.scenarios}, {"retention", "expiration", "deletion", "tenant"})

    def test_unknown_fields_versions_nonfiction_and_invalid_times(self):
        documents = []
        for field, value in (("schema_version", "2.0"), ("fictional", False), ("extra", 1)):
            changed = self.document()
            changed[field] = value
            documents.append(changed)
        for field, value in (("at", -1), ("at", True), ("tenant", ""), ("op", "reopen")):
            changed = self.document()
            changed["scenarios"][0]["events"][0][field] = value
            documents.append(changed)
        backwards = self.document()
        backwards["scenarios"][0]["events"][2]["at"] = 0
        documents.append(backwards)
        for index, document in enumerate(documents):
            with self.subTest(case=index), self.assertRaises(ValidationError):
                parse_suite(document)

    def test_memory_id_collision_and_duplicate_probe_are_rejected(self):
        document = self.document()
        changed = deepcopy(document["scenarios"][0]["events"][0])
        changed["memory"]["value"] = "different"
        document["scenarios"][0]["events"].insert(1, changed)
        with self.assertRaises(ValidationError):
            parse_suite(document)
        document = self.document()
        document["scenarios"][0]["events"].append(deepcopy(document["scenarios"][0]["events"][-1]))
        with self.assertRaises(ValidationError):
            parse_suite(document)

    def test_malformed_duplicate_key_and_oversized_json_are_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for data in (b"{", b'{"schema_version":"1.0","schema_version":"2.0"}',
                         b" " * (MAX_BYTES + 1), b'{"at":NaN}'):
                with self.subTest(data_length=len(data)):
                    path.write_bytes(data)
                    with self.assertRaises(ValidationError):
                        load_suite(path)

    def test_boolean_expiry_and_inconsistent_expected_answer_are_rejected(self):
        document = self.document()
        document["scenarios"][0]["events"][0]["memory"]["expires_at"] = True
        with self.assertRaises(ValidationError):
            parse_suite(document)
        document = self.document()
        document["scenarios"][0]["events"][1]["expected"]["evidence_ids"] = []
        with self.assertRaises(ValidationError):
            parse_suite(document)


class HarnessScoringTests(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(SMOKE)

    def test_reference_smoke_has_positive_controls_and_exact_outcomes(self):
        report, traces = evaluate(self.suite, "conservative")
        self.assertTrue(report["passed"])
        self.assertEqual(report["execution_kind"], "offline_mock")
        self.assertEqual(report["summary"]["tasks"], {"passed": 9, "total": 9})
        self.assertEqual(report["summary"]["positive_answers"], {"passed": 7, "total": 7})
        self.assertEqual(report["summary"]["required_abstentions"], {"passed": 2, "total": 2})
        self.assertEqual(report["summary"]["contract_violations"], 0)
        self.assertEqual(report["summary"]["total"], 27)
        self.assertEqual(len(traces), 41)
        for category in ("expiration", "deletion"):
            controls = [c for c in report["checks"] if c["category"] == category
                        and c["type"] == "probe" and c["reason"] == "present"]
            self.assertEqual({c["path"] for c in controls}, {"search", "get"})
            self.assertTrue(all(c["passed"] and c["expected_ids"] for c in controls))
        boundary = [c for c in report["checks"] if c["category"] == "expiration"
                    and c["type"] == "probe" and c["at"] == 10]
        self.assertEqual({c["path"] for c in boundary}, {"search", "get"})
        self.assertTrue(all(c["observed_ids"] == () for c in boundary))

    def test_empty_adapter_cannot_get_utility_pass(self):
        report, _ = evaluate(self.suite, "conservative", EmptyStore)
        self.assertFalse(report["passed"])
        self.assertEqual(report["summary"]["contract_violations"], 0)
        self.assertEqual(report["summary"]["positive_answers"], {"passed": 0, "total": 7})
        self.assertEqual(report["summary"]["required_abstentions"], {"passed": 2, "total": 2})

    def test_scorer_detects_expiry_get_path_defect(self):
        report, _ = evaluate(self.suite, "conservative", ExpiredGetStore)
        self.assertFalse(report["passed"])
        self.assertEqual(report["supported_paths"]["get"]["violations"]["expired"], 2)
        self.assertEqual(report["supported_paths"]["search"]["violations"]["expired"], 0)

    def test_scorer_detects_deleted_get_cache_defect(self):
        report, _ = evaluate(self.suite, "conservative", DeletedGetStore)
        self.assertFalse(report["passed"])
        self.assertGreater(report["supported_paths"]["get"]["violations"]["deleted"], 0)
        self.assertEqual(report["supported_paths"]["search"]["violations"]["deleted"], 0)

    def test_scorer_detects_tenant_search_defect(self):
        report, _ = evaluate(self.suite, "conservative", ForeignSearchStore)
        self.assertFalse(report["passed"])
        self.assertGreater(report["supported_paths"]["search"]["violations"]["tenant"], 0)

    def test_scorer_rejects_known_record_for_wrong_read_parameters(self):
        ledger = LifecycleLedger()
        record = Memory("tenant-a", "known-record", "fictional-person", "channel", "email",
                        0, 0, None, "fictional wrong-scope test")
        ledger.put(record)
        for path, inputs in (("get", {"memory_id": "different-record"}),
                             ("search", {"subject": "different-person", "key": "channel"})):
            with self.subTest(path=path):
                observation = ReadObservation(path, "tenant-a", 0, inputs, (record,))
                self.assertEqual([v["kind"] for v in ledger.inspect(observation)], ["unexpected_record"])

    def test_backend_exception_is_not_a_correct_abstention(self):
        report, _ = evaluate(self.suite, "conservative", FailingReadStore)
        self.assertFalse(report["passed"])
        self.assertEqual(report["summary"]["required_abstentions"], {"passed": 0, "total": 2})
        self.assertTrue(all(c["observed"]["status"] == "error"
                            for c in report["checks"] if c["type"] == "task"))
        self.assertGreater(report["summary"]["contract_violations"], 0)

    def test_only_public_query_fields_are_passed_to_agent(self):
        seen = []

        def observing_agent(query, tools, policy):
            self.assertIs(type(query), Query)
            self.assertEqual({f.name for f in fields(query)}, {"subject", "key", "description"})
            self.assertFalse(hasattr(query, "expected"))
            seen.append(query)
            return real_answer(query, tools, policy)

        with patch("memory_lifecycle_bench.runner.answer", observing_agent):
            evaluate(self.suite, "conservative")
        self.assertEqual(len(seen), 9)

    def test_reports_are_deterministic_and_citations_link_to_trace(self):
        first, trace_a = evaluate(self.suite, "conservative")
        second, trace_b = evaluate(self.suite, "conservative")
        self.assertEqual(first, second)
        self.assertEqual(trace_a, trace_b)
        trace_ids = {r["trace_id"] for r in trace_a if r["type"] == "read"}
        self.assertTrue(all(ref in trace_ids for c in first["checks"] for ref in c["trace_refs"]))
        with TemporaryDirectory() as directory:
            write_reports(directory, first, trace_a)
            loaded = json.loads((Path(directory) / "report.json").read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in (Path(directory) / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(loaded["suite_sha256"], self.suite.digest)
            self.assertEqual(len(rows), 41)


class CliTests(unittest.TestCase):
    def test_validate_and_strict_smoke(self):
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            self.assertEqual(main(["validate", str(SMOKE)]), 0)
            self.assertEqual(main(["run", str(SMOKE), "--out", directory, "--strict"]), 0)
            self.assertTrue((Path(directory) / "report.json").is_file())

    def test_strict_task_failure_and_observation_mode_exit_codes(self):
        document = json.loads(SMOKE.read_text(encoding="utf-8"))
        document["scenarios"][0]["events"][1]["expected"]["value"] = "deliberately-wrong-fictional-gold"
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            path = Path(directory) / "wrong-gold.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            out = str(Path(directory) / "reports")
            self.assertEqual(main(["run", str(path), "--out", out, "--strict"]), 1)
            self.assertEqual(main(["run", str(path), "--out", out]), 0)
            self.assertFalse(json.loads((Path(out) / "report.json").read_text(encoding="utf-8"))["passed"])

    def test_invalid_input_is_exit_two_without_traceback(self):
        with TemporaryDirectory() as directory, redirect_stderr(StringIO()) as error:
            path = Path(directory) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(main(["validate", str(path)]), 2)
            self.assertIn("INVALID INPUT", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())


if __name__ == "__main__":
    unittest.main()
