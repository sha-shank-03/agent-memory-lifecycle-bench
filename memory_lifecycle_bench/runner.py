"""Virtual-time fixture orchestration, read traces, and Report 1.0 generation."""

from dataclasses import asdict
from pathlib import Path
import json
import platform
import sqlite3
from tempfile import TemporaryDirectory
from typing import Callable

from . import __version__
from .agent import MOCK_VERSION, POLICIES, TenantMemoryTools, ToolExecutionError, answer, retention_seconds
from .model import CONTRACT_VERSION, ReadObservation, Store, VirtualClock
from .scoring import LifecycleLedger, VIOLATIONS, score_answer, score_probe
from .store import SCHEMA_VERSION, SQLiteStore
from .suite import Delete, Probe, Put, Reopen, SUITE_VERSION, Suite, Task

REPORT_VERSION = "1.0"


def evaluate(suite: Suite, policy: str, store_factory: Callable[[Path], Store] = SQLiteStore) -> tuple[dict, list[dict]]:
    if policy not in POLICIES:
        raise ValueError(f"unsupported policy: {policy}")
    checks: list[dict] = []
    traces: list[dict] = []
    path_counts = {path: {"reads": 0, "violations": {kind: 0 for kind in VIOLATIONS}}
                   for path in ("search", "get")}
    with TemporaryDirectory(prefix="memory-lifecycle-") as directory:
        for scenario_index, scenario in enumerate(suite.scenarios):
            # Backend paths carry an ordinal, not the private scenario label.
            database_path = Path(directory) / f"scenario-{scenario_index}.sqlite"
            store = store_factory(database_path)
            ledger, clock = LifecycleLedger(), VirtualClock()
            try:
                for event_index, event in enumerate(scenario.events):
                    clock.advance(event.at)
                    base = {"scenario": scenario.scenario_id, "category": scenario.category,
                            "event_index": event_index, "at": clock.now}
                    if isinstance(event, Reopen):
                        store.close()
                        store = store_factory(database_path)
                        traces.append({**base, "type": "reopen", "closed": True, "reopened": True})
                        continue
                    if isinstance(event, Put):
                        inserted = store.put(event.memory)
                        ledger.put(event.memory)
                        traces.append({**base, "type": "put", "memory": asdict(event.memory), "inserted": inserted})
                        continue
                    if isinstance(event, Delete):
                        changed = store.delete(event.tenant_id, event.memory_id)
                        ledger.delete(event.tenant_id, event.memory_id)
                        traces.append({**base, "type": "delete", "tenant_id": event.tenant_id,
                                       "memory_id": event.memory_id, "changed": changed})
                        continue
                    tools = TenantMemoryTools(store, event.tenant_id, clock.now,
                                              max_age_seconds=retention_seconds(policy))
                    if isinstance(event, Task):
                        result = answer(event.query, tools, policy)
                        check = {**base, "id": event.task_id, "type": "task", "tenant_id": event.tenant_id,
                                 "task": asdict(event.query), **score_answer(event.expected, result)}
                    else:
                        assert isinstance(event, Probe)
                        try:
                            if event.path == "search":
                                tools.search(**event.inputs)
                            else:
                                tools.get(**event.inputs)
                        except ToolExecutionError:
                            pass  # Error remains in the observation and fails the probe/contract.
                        check = {**base, "id": event.probe_id, "type": "probe", "tenant_id": event.tenant_id,
                                 "path": event.path, "reason": event.reason,
                                 **score_probe(event.expected_ids, tools.observations[0])}
                    check["trace_refs"] = []
                    check["contract_violations"] = []
                    check["retention_excluded_ids"] = []
                    for read_index, observation in enumerate(tools.observations):
                        trace_id = f"{scenario.scenario_id}.e{event_index}.r{read_index}"
                        violations = ledger.inspect(observation)
                        path_counts[observation.path]["reads"] += 1
                        for violation in violations:
                            path_counts[observation.path]["violations"][violation["kind"]] += 1
                        traces.append({**base, "type": "read", "trace_id": trace_id,
                                       **asdict(observation), "contract_violations": violations,
                                       "delivered_memory_ids": [m.memory_id for m in observation.visible_memories]})
                        check["trace_refs"].append(trace_id)
                        check["contract_violations"].extend(violations)
                        check["retention_excluded_ids"].extend(observation.excluded_by_retention)
                    if check["contract_violations"]:
                        check["passed"] = False
                        check["failures"].append("supported retrieval contract violated")
                    checks.append(check)
            finally:
                store.close()

    tasks = [c for c in checks if c["type"] == "task"]
    positives = [c for c in tasks if c["expected"]["status"] == "answer"]
    abstentions = [c for c in tasks if c["expected"]["status"] != "answer"]
    categories = {}
    for category in sorted({s.category for s in suite.scenarios}):
        category_checks = [c for c in checks if c["category"] == category]
        categories[category] = {kind: {"passed": sum(c["passed"] for c in category_checks if c["type"] == kind),
                                      "total": sum(c["type"] == kind for c in category_checks)}
                                for kind in ("task", "probe")}
    report = {
        "schema_version": REPORT_VERSION, "suite_schema_version": SUITE_VERSION,
        "store_contract_version": CONTRACT_VERSION, "sqlite_schema_version": SCHEMA_VERSION,
        "tool_version": __version__, "mock_agent_version": MOCK_VERSION,
        "execution_kind": "offline_mock", "suite_id": suite.suite_id, "suite_sha256": suite.digest,
        "policy": policy, "policy_version": "1.0",
        "retention": "unbounded" if retention_seconds(policy) is None else "seven-days",
        "retention_seconds": retention_seconds(policy), "scenario_count": len(suite.scenarios),
        "adapter": getattr(store_factory, "__name__", "trusted-adapter"),
        "runtime": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version},
        "summary": {"passed": sum(c["passed"] for c in checks), "total": len(checks),
                    "tasks": {"passed": sum(c["passed"] for c in tasks), "total": len(tasks)},
                    "positive_answers": {"passed": sum(c["passed"] for c in positives), "total": len(positives)},
                    "required_abstentions": {"passed": sum(c["passed"] for c in abstentions), "total": len(abstentions)},
                    "contract_violations": sum(sum(p["violations"].values()) for p in path_counts.values()),
                    "stale_answers": sum(c["category"] == "stale" and c["observed"]["status"] == "answer"
                                         and c["observed"]["value"] != c["expected"]["value"] for c in tasks),
                    "confident_conflict_errors": sum(c["expected"]["status"] == "conflict"
                                                     and c["observed"]["status"] == "answer" for c in tasks),
                    "retention_task_losses": sum(c["expected"]["status"] == "answer"
                                                 and c["observed"]["status"] == "unknown"
                                                 and bool(c["retention_excluded_ids"]) for c in tasks),
                    "reopens": sum(t["type"] == "reopen" for t in traces)},
        "categories": categories, "supported_paths": path_counts,
        "passed": all(c["passed"] for c in checks), "checks": checks, "trace_file": "trace.jsonl",
    }
    return report, traces


def compare(suite: Suite, out_dir: str | Path) -> dict:
    """Completion is separate from aggregate pass: any baseline failure stays false."""
    out = Path(out_dir)
    configurations = []
    for policy in POLICIES:
        report, traces = evaluate(suite, policy)
        write_reports(out / policy, report, traces)
        configurations.append({"policy": policy, "passed": report["passed"],
                               "summary": report["summary"], "categories": report["categories"],
                               "supported_paths": report["supported_paths"],
                               "retention_seconds": report["retention_seconds"],
                               "report_file": f"{policy}/report.json"})
    comparison = {"schema_version": REPORT_VERSION, "execution_kind": "offline_mock",
                  "suite_id": suite.suite_id, "suite_sha256": suite.digest,
                  "completed": True, "passed": all(r["passed"] for r in configurations),
                  "configurations": configurations}
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return comparison


def write_reports(out_dir: str | Path, report: dict, traces: list[dict]) -> None:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    # Canonical JSON has no wall-clock timestamp or timing-derived metric.
    (path / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (path / "trace.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in traces), encoding="utf-8")


def terminal_summary(report: dict) -> str:
    summary = report["summary"]
    lines = [f"OFFLINE MOCK | {report['suite_id']} | policy={report['policy']}",
             f"scenarios={report['scenario_count']} checks={summary['passed']}/{summary['total']}",
             f"tasks={summary['tasks']['passed']}/{summary['tasks']['total']} "
             f"positive_answers={summary['positive_answers']['passed']}/{summary['positive_answers']['total']} "
             f"required_abstentions={summary['required_abstentions']['passed']}/{summary['required_abstentions']['total']}",
             f"contract_violations={summary['contract_violations']}"]
    for path, metrics in report["supported_paths"].items():
        counts = metrics["violations"]
        lines.append(f"{path}: reads={metrics['reads']} deleted={counts['deleted']} "
                     f"expired={counts['expired']} tenant={counts['tenant']}")
    for category, counts in report["categories"].items():
        lines.append(f"{category}: tasks={counts['task']['passed']}/{counts['task']['total']} "
                     f"probes={counts['probe']['passed']}/{counts['probe']['total']}")
    for check in report["checks"]:
        if not check["passed"]:
            lines.append(f"FAIL {check['scenario']}/{check['id']}: {'; '.join(check['failures'])}")
    return "\n".join(lines)
