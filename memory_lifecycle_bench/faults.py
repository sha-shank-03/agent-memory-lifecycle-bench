"""Fixed fictional diagnostics, never fault switches for caller-supplied suites."""

from hashlib import sha256
from pathlib import Path

from .runner import evaluate, write_reports
from .store import SQLiteStore
from .suite import load_suite_bytes

FAULTS = ("expired-get", "deleted-search", "tenant-search")

# These literal inputs include independent positive and negative expectations.
# Faults alter adapter behavior, not these input bytes or the evaluator's oracle.
_INPUTS = {
    "expired-get": '''{
  "schema_version":"1.0","suite_id":"fault-expired-get","fictional":true,
  "scenarios":[{"id":"fixed-expiry","category":"expiration","events":[
    {"op":"put","at":0,"tenant":"northwind","memory":{"id":"fixed-trial","subject":"fictional-trial","key":"queue","value":"trial-support","recorded_at":0,"effective_at":0,"expires_at":10,"source":"fixed fictional diagnostic"}},
    {"op":"query","at":9,"tenant":"northwind","id":"positive-task","task":{"subject":"fictional-trial","key":"queue","description":"Which fictional queue exists before expiry?"},"expected":{"status":"answer","value":"trial-support","evidence_ids":["fixed-trial"]}},
    {"op":"probe","at":9,"tenant":"northwind","id":"positive-search","path":"search","inputs":{"subject":"fictional-trial","key":"queue"},"expected_ids":["fixed-trial"],"reason":"present"},
    {"op":"probe","at":9,"tenant":"northwind","id":"positive-get","path":"get","inputs":{"memory_id":"fixed-trial"},"expected_ids":["fixed-trial"],"reason":"present"},
    {"op":"query","at":10,"tenant":"northwind","id":"expired-task","task":{"subject":"fictional-trial","key":"queue","description":"Which active queue is supported at exact expiry?"},"expected":{"status":"unknown","value":null,"evidence_ids":[]}},
    {"op":"probe","at":10,"tenant":"northwind","id":"expired-search","path":"search","inputs":{"subject":"fictional-trial","key":"queue"},"expected_ids":[],"reason":"expired"},
    {"op":"probe","at":10,"tenant":"northwind","id":"expired-get","path":"get","inputs":{"memory_id":"fixed-trial"},"expected_ids":[],"reason":"expired"},
    {"op":"probe","at":11,"tenant":"northwind","id":"after-expired-get","path":"get","inputs":{"memory_id":"fixed-trial"},"expected_ids":[],"reason":"expired"}
  ]}]
}
''',
    "deleted-search": '''{
  "schema_version":"1.0","suite_id":"fault-deleted-search","fictional":true,
  "scenarios":[{"id":"fixed-deletion","category":"deletion","events":[
    {"op":"put","at":0,"tenant":"northwind","memory":{"id":"fixed-forgotten","subject":"fictional-forgotten","key":"queue","value":"core-support","recorded_at":0,"effective_at":0,"expires_at":null,"source":"fixed fictional diagnostic"}},
    {"op":"query","at":1,"tenant":"northwind","id":"positive-task","task":{"subject":"fictional-forgotten","key":"queue","description":"Which fictional queue exists before deletion?"},"expected":{"status":"answer","value":"core-support","evidence_ids":["fixed-forgotten"]}},
    {"op":"probe","at":1,"tenant":"northwind","id":"positive-search","path":"search","inputs":{"subject":"fictional-forgotten","key":"queue"},"expected_ids":["fixed-forgotten"],"reason":"present"},
    {"op":"probe","at":1,"tenant":"northwind","id":"positive-get","path":"get","inputs":{"memory_id":"fixed-forgotten"},"expected_ids":["fixed-forgotten"],"reason":"present"},
    {"op":"delete","at":2,"tenant":"northwind","memory_id":"fixed-forgotten"},
    {"op":"query","at":2,"tenant":"northwind","id":"deleted-task","task":{"subject":"fictional-forgotten","key":"queue","description":"Which supported queue remains after forgetting?"},"expected":{"status":"unknown","value":null,"evidence_ids":[]}},
    {"op":"probe","at":2,"tenant":"northwind","id":"deleted-search","path":"search","inputs":{"subject":"fictional-forgotten","key":"queue"},"expected_ids":[],"reason":"deleted"},
    {"op":"probe","at":2,"tenant":"northwind","id":"deleted-get","path":"get","inputs":{"memory_id":"fixed-forgotten"},"expected_ids":[],"reason":"deleted"}
  ]}]
}
''',
    "tenant-search": '''{
  "schema_version":"1.0","suite_id":"fault-tenant-search","fictional":true,
  "scenarios":[{"id":"fixed-tenant","category":"tenant","events":[
    {"op":"put","at":0,"tenant":"northwind","memory":{"id":"fixed-shared","subject":"fictional-shared-customer","key":"queue","value":"north-queue","recorded_at":0,"effective_at":0,"expires_at":null,"source":"fixed fictional north diagnostic"}},
    {"op":"put","at":0,"tenant":"southwind","memory":{"id":"fixed-shared","subject":"fictional-shared-customer","key":"queue","value":"south-queue","recorded_at":0,"effective_at":0,"expires_at":null,"source":"fixed fictional south diagnostic"}},
    {"op":"query","at":1,"tenant":"northwind","id":"positive-north","task":{"subject":"fictional-shared-customer","key":"queue","description":"Which fictional north queue applies?"},"expected":{"status":"answer","value":"north-queue","evidence_ids":["fixed-shared"]}},
    {"op":"query","at":1,"tenant":"southwind","id":"positive-south","task":{"subject":"fictional-shared-customer","key":"queue","description":"Which fictional south queue applies?"},"expected":{"status":"answer","value":"south-queue","evidence_ids":["fixed-shared"]}},
    {"op":"probe","at":1,"tenant":"northwind","id":"positive-search","path":"search","inputs":{"subject":"fictional-shared-customer","key":"queue"},"expected_ids":["fixed-shared"],"reason":"present"},
    {"op":"probe","at":1,"tenant":"southwind","id":"positive-get","path":"get","inputs":{"memory_id":"fixed-shared"},"expected_ids":["fixed-shared"],"reason":"present"},
    {"op":"query","at":2,"tenant":"westwind","id":"foreign-task","task":{"subject":"fictional-shared-customer","key":"queue","description":"Is there a supported west tenant queue?"},"expected":{"status":"unknown","value":null,"evidence_ids":[]}},
    {"op":"probe","at":2,"tenant":"westwind","id":"foreign-search","path":"search","inputs":{"subject":"fictional-shared-customer","key":"queue"},"expected_ids":[],"reason":"tenant"},
    {"op":"probe","at":2,"tenant":"westwind","id":"foreign-get","path":"get","inputs":{"memory_id":"fixed-shared"},"expected_ids":[],"reason":"tenant"}
  ]}]
}
''',
}


class ExpiredGetFault(SQLiteStore):
    def get(self, tenant_id, memory_id, at):
        return super().get(tenant_id, memory_id, min(at, 9))


class DeletedSearchFault(SQLiteStore):
    def __init__(self, path):
        super().__init__(path)
        self._stale = {}

    def delete(self, tenant_id, memory_id):
        before = super().get(tenant_id, memory_id, 0)
        changed = super().delete(tenant_id, memory_id)
        if changed and before:
            self._stale[(tenant_id, before.subject, before.key)] = before
        return changed

    def search(self, tenant_id, subject, key, at):
        result = super().search(tenant_id, subject, key, at)
        stale = self._stale.get((tenant_id, subject, key))
        return result or ((stale,) if stale else ())


class TenantSearchFault(SQLiteStore):
    def search(self, tenant_id, subject, key, at):
        injected_tenant = "northwind" if tenant_id == "westwind" else tenant_id
        return super().search(injected_tenant, subject, key, at)


def fault_input_bytes(fault: str) -> bytes:
    if fault not in FAULTS:
        raise ValueError(f"unsupported fixed fault: {fault}")
    return _INPUTS[fault].encode("utf-8")


def run_fault_demo(fault: str, out_dir: str | Path) -> dict:
    raw = fault_input_bytes(fault)
    digest = sha256(raw).hexdigest()
    reference, reference_traces = evaluate(load_suite_bytes(raw), "conservative")
    factory = {"expired-get": ExpiredGetFault, "deleted-search": DeletedSearchFault,
               "tenant-search": TenantSearchFault}[fault]
    report, traces = evaluate(load_suite_bytes(raw), "conservative", factory)
    path, kind = {"expired-get": ("get", "expired"), "deleted-search": ("search", "deleted"),
                  "tenant-search": ("search", "tenant")}[fault]
    positive_ids = {(c["scenario"], c["id"]) for c in reference["checks"]
                    if (c["type"] == "task" and c["expected"]["status"] == "answer")
                    or (c["type"] == "probe" and c["reason"] == "present")}
    positives = [c for c in report["checks"] if (c["scenario"], c["id"]) in positive_ids]
    preserved = bool(positives) and all(c["passed"] for c in positives)
    observed = report["supported_paths"][path]["violations"][kind]
    unchanged = fault_input_bytes(fault) == raw and reference["suite_sha256"] == report["suite_sha256"] == digest
    report["fault_demo"] = {"fault": fault, "expected_path": path, "expected_violation": kind,
                            "violation_count": observed, "positive_controls_preserved": preserved,
                            "positive_control_count": len(positives), "input_bytes_unchanged": unchanged,
                            "reference_passed": reference["passed"], "input_file": "input.json",
                            "reference_report": "reference/report.json",
                            "diagnostic_valid": reference["passed"] and preserved and unchanged and observed > 0}
    out = Path(out_dir)
    write_reports(out / "reference", reference, reference_traces)
    write_reports(out, report, traces)
    (out / "input.json").write_bytes(raw)
    return report
