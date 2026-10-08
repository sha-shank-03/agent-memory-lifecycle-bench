"""Bounded Suite 1.0 validation and evaluator-owned expectations."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .model import Memory, Query, ValidationError, identifier, seconds, text_value

SUITE_VERSION = "1.0"
MAX_BYTES = 1024 * 1024
CATEGORIES = ("retention", "expiration", "deletion", "tenant", "stale", "conflict")


@dataclass(frozen=True)
class ExpectedAnswer:
    status: str
    value: str | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class Put:
    at: int
    memory: Memory


@dataclass(frozen=True)
class Delete:
    at: int
    tenant_id: str
    memory_id: str


@dataclass(frozen=True)
class Reopen:
    at: int


@dataclass(frozen=True)
class Task:
    at: int
    tenant_id: str
    task_id: str
    query: Query
    expected: ExpectedAnswer


@dataclass(frozen=True)
class Probe:
    at: int
    tenant_id: str
    probe_id: str
    path: str
    inputs: dict[str, str]
    expected_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    category: str
    events: tuple[Put | Delete | Reopen | Task | Probe, ...]


@dataclass(frozen=True)
class Suite:
    suite_id: str
    scenarios: tuple[Scenario, ...]
    digest: str


def _object(value: Any, required: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{where}: expected object")
    missing, extra = required - value.keys(), value.keys() - required
    if missing or extra:
        raise ValidationError(f"{where}: missing={sorted(missing)}, unknown={sorted(extra)}")
    return value


def _array(value: Any, where: str, maximum: int, minimum: int = 0) -> list[Any]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValidationError(f"{where}: expected array of {minimum}..{maximum} items")
    return value


def _ids(value: Any, where: str) -> tuple[str, ...]:
    ids = tuple(identifier(x, where) for x in _array(value, where, 64))
    if len(ids) != len(set(ids)):
        raise ValidationError(f"{where}: duplicate IDs")
    return tuple(sorted(ids))


def _expectation(value: Any, where: str) -> ExpectedAnswer:
    obj = _object(value, {"status", "value", "evidence_ids"}, where)
    status = obj["status"]
    if status not in ("answer", "unknown", "conflict"):
        raise ValidationError(f"{where}.status: expected answer, unknown, or conflict")
    ids = _ids(obj["evidence_ids"], f"{where}.evidence_ids")
    if status == "answer":
        text_value(obj["value"], f"{where}.value")
        if len(ids) != 1:
            raise ValidationError(f"{where}: an answer requires exactly one evidence ID")
    elif obj["value"] is not None:
        raise ValidationError(f"{where}: abstention value must be null")
    if status == "unknown" and ids:
        raise ValidationError(f"{where}: unknown must have no evidence IDs")
    if status == "conflict" and len(ids) < 2:
        raise ValidationError(f"{where}: conflict requires at least two evidence IDs")
    return ExpectedAnswer(status, obj["value"], ids)


def parse_suite(document: Any, digest: str | None = None) -> Suite:
    root = _object(document, {"schema_version", "suite_id", "fictional", "scenarios"}, "suite")
    if root["schema_version"] != SUITE_VERSION:
        raise ValidationError("suite.schema_version: only 1.0 is supported")
    if root["fictional"] is not True:
        raise ValidationError("suite.fictional: must be true; use fictional data only")
    suite_id = identifier(root["suite_id"], "suite.suite_id")
    scenarios: list[Scenario] = []
    scenario_ids: set[str] = set()
    for index, raw in enumerate(_array(root["scenarios"], "suite.scenarios", 100, 1)):
        where = f"scenarios[{index}]"
        scenario = _object(raw, {"id", "category", "events"}, where)
        scenario_id = identifier(scenario["id"], f"{where}.id")
        if scenario_id in scenario_ids:
            raise ValidationError(f"{where}.id: duplicate scenario ID")
        scenario_ids.add(scenario_id)
        category = scenario["category"]
        if category not in CATEGORIES:
            raise ValidationError(f"{where}.category: unsupported category")
        events: list[Put | Delete | Reopen | Task | Probe] = []
        records: dict[tuple[str, str], Memory] = {}
        versions: dict[tuple[str, str, str], int] = {}
        check_ids: set[str] = set()
        now = 0
        for event_index, raw_event in enumerate(_array(scenario["events"], f"{where}.events", 500, 1)):
            event_where = f"{where}.events[{event_index}]"
            if not isinstance(raw_event, dict):
                raise ValidationError(f"{event_where}: expected object")
            op = raw_event.get("op")
            keys = {
                "put": {"op", "at", "tenant", "memory"},
                "delete": {"op", "at", "tenant", "memory_id"},
                "reopen": {"op", "at"},
                "query": {"op", "at", "tenant", "id", "task", "expected"},
                "probe": {"op", "at", "tenant", "id", "path", "inputs", "expected_ids", "reason"},
            }
            if not isinstance(op, str) or op not in keys:
                raise ValidationError(f"{event_where}.op: unsupported operation")
            event = _object(raw_event, keys[op], event_where)
            at = seconds(event["at"], f"{event_where}.at")
            if at < now:
                raise ValidationError(f"{event_where}.at: event clock cannot move backwards")
            now = at
            if op == "reopen":
                events.append(Reopen(at))
                continue
            tenant = identifier(event["tenant"], f"{event_where}.tenant")
            if op == "put":
                memory_obj = _object(event["memory"], {
                    "id", "subject", "key", "value", "recorded_at", "effective_at", "expires_at", "source"
                }, f"{event_where}.memory")
                memory = Memory(tenant, memory_obj["id"], memory_obj["subject"], memory_obj["key"],
                                memory_obj["value"], memory_obj["recorded_at"], memory_obj["effective_at"],
                                memory_obj["expires_at"], memory_obj["source"])
                memory.validate()
                if memory.recorded_at > at:
                    raise ValidationError(f"{event_where}: recorded_at cannot be after the put event")
                identity = (tenant, memory.memory_id)
                if identity in records and records[identity] != memory:
                    raise ValidationError(f"{event_where}: memory ID reused with different content")
                if identity not in records:
                    fact = (tenant, memory.subject, memory.key)
                    versions[fact] = versions.get(fact, 0) + 1
                    if versions[fact] > 64:
                        raise ValidationError(f"{event_where}: more than 64 versions of one fact")
                records[identity] = memory
                events.append(Put(at, memory))
            elif op == "delete":
                events.append(Delete(at, tenant, identifier(event["memory_id"], f"{event_where}.memory_id")))
            else:
                check_id = identifier(event["id"], f"{event_where}.id")
                if check_id in check_ids:
                    raise ValidationError(f"{event_where}.id: duplicate query/probe ID")
                check_ids.add(check_id)
                if op == "query":
                    task = _object(event["task"], {"subject", "key", "description"}, f"{event_where}.task")
                    query = Query(identifier(task["subject"], "task.subject"), identifier(task["key"], "task.key"),
                                  text_value(task["description"], "task.description"))
                    events.append(Task(at, tenant, check_id, query,
                                       _expectation(event["expected"], f"{event_where}.expected")))
                else:
                    path = event["path"]
                    if path not in ("search", "get"):
                        raise ValidationError(f"{event_where}.path: expected search or get")
                    fields = {"subject", "key"} if path == "search" else {"memory_id"}
                    inputs = _object(event["inputs"], fields, f"{event_where}.inputs")
                    inputs = {name: identifier(val, f"{event_where}.inputs.{name}") for name, val in inputs.items()}
                    reason = event["reason"]
                    if reason not in ("present", "expired", "deleted", "tenant", "future", "absent"):
                        raise ValidationError(f"{event_where}.reason: unsupported probe reason")
                    events.append(Probe(at, tenant, check_id, path, inputs,
                                        _ids(event["expected_ids"], f"{event_where}.expected_ids"), reason))
        if not check_ids:
            raise ValidationError(f"{where}: must contain at least one query or probe")
        scenarios.append(Scenario(scenario_id, category, tuple(events)))
    if digest is None:
        digest = sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return Suite(suite_id, tuple(scenarios), digest)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"JSON contains duplicate object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValidationError(f"JSON constant is unsupported: {value}")


def load_suite_bytes(raw: bytes) -> Suite:
    if len(raw) > MAX_BYTES:
        raise ValidationError("suite exceeds 1 MiB input limit")
    try:
        document = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValidationError(f"invalid UTF-8 JSON: {exc}") from exc
    return parse_suite(document, sha256(raw).hexdigest())


def load_suite(path: str | Path) -> Suite:
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    return load_suite_bytes(raw)
