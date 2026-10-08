"""Evaluator-owned scoring. No policy selection function or store queries here."""

from dataclasses import asdict

from .model import Answer, Memory, ReadObservation
from .suite import ExpectedAnswer

VIOLATIONS = ("deleted", "expired", "tenant", "future", "unexpected_record", "corrupt_payload", "backend_error")


class LifecycleLedger:
    """Tracks fixture writes/deletes independently of the adapter's persisted state."""

    def __init__(self) -> None:
        self.records: dict[tuple[str, str], Memory] = {}
        self.deleted: set[tuple[str, str]] = set()

    def put(self, memory: Memory) -> None:
        self.records[(memory.tenant_id, memory.memory_id)] = memory

    def delete(self, tenant_id: str, memory_id: str) -> None:
        identity = (tenant_id, memory_id)
        if identity in self.records:
            self.deleted.add(identity)

    def inspect(self, observation: ReadObservation) -> list[dict[str, str]]:
        if observation.error:
            return [{"kind": "backend_error", "detail": observation.error}]
        violations: list[dict[str, str]] = []
        for memory in observation.memories:
            identity = (memory.tenant_id, memory.memory_id)
            expected = self.records.get(identity)
            kinds: list[str] = []
            if memory.tenant_id != observation.tenant_id:
                kinds.append("tenant")
            wrong_scope = (
                observation.path == "get" and memory.memory_id != observation.inputs["memory_id"]
            ) or (
                observation.path == "search"
                and (memory.subject != observation.inputs["subject"] or memory.key != observation.inputs["key"])
            )
            if expected is None or wrong_scope:
                kinds.append("unexpected_record")
            if expected is not None:
                if identity in self.deleted:
                    kinds.append("deleted")
                if expected.expires_at is not None and observation.at >= expected.expires_at:
                    kinds.append("expired")
                if observation.at < expected.effective_at:
                    kinds.append("future")
                if memory != expected:
                    kinds.append("corrupt_payload")
            violations.extend({"kind": kind, "memory_id": memory.memory_id} for kind in kinds)
        return violations


def score_answer(expected: ExpectedAnswer, observed: Answer) -> dict:
    expected_json = asdict(expected)
    observed_json = asdict(observed)
    differences = []
    for field in ("status", "value", "evidence_ids"):
        if getattr(expected, field) != getattr(observed, field):
            differences.append(f"{field} differs")
    if observed.error:
        differences.append(f"execution error: {observed.error}")
    return {"passed": not differences, "expected": expected_json, "observed": observed_json,
            "failures": differences}


def score_probe(expected_ids: tuple[str, ...], observation: ReadObservation) -> dict:
    observed_ids = tuple(sorted(m.memory_id for m in observation.visible_memories))
    failures = []
    if observed_ids != expected_ids:
        failures.append("returned memory IDs differ")
    if observation.error:
        failures.append(f"execution error: {observation.error}")
    return {"passed": not failures, "expected_ids": expected_ids, "observed_ids": observed_ids,
            "failures": failures}
