"""Deterministic mock execution. No oracle input, model, or retained task context."""

from .model import Answer, Memory, Query, ReadObservation, Store, identifier, seconds

POLICIES = ("last-write", "short-window", "valid-time", "conservative")
MOCK_VERSION = "1.0"
SHORT_WINDOW_SECONDS = 604800


def retention_seconds(policy: str) -> int | None:
    if policy not in POLICIES:
        raise ValueError(f"unsupported policy: {policy}")
    return SHORT_WINDOW_SECONDS if policy == "short-window" else None


class ToolExecutionError(RuntimeError):
    pass


class TenantMemoryTools:
    """Read tool parameters contain no tenant override or administrative read."""

    def __init__(self, store: Store, tenant_id: str, at: int, max_calls: int = 2,
                 max_age_seconds: int | None = None) -> None:
        self._store = store
        self._tenant_id = identifier(tenant_id, "tenant_id")
        self._at = seconds(at, "at")
        self._max_calls = max_calls
        self._max_age_seconds = max_age_seconds
        self.observations: list[ReadObservation] = []

    def _read(self, path: str, inputs: dict[str, str]) -> tuple[Memory, ...]:
        if len(self.observations) >= self._max_calls:
            raise ToolExecutionError("read-tool call budget exhausted")
        try:
            if path == "search":
                result = self._store.search(self._tenant_id, inputs["subject"], inputs["key"], self._at)
            else:
                memory = self._store.get(self._tenant_id, inputs["memory_id"], self._at)
                result = () if memory is None else (memory,)
            if not isinstance(result, tuple) or not all(isinstance(m, Memory) for m in result):
                raise TypeError("store returned an invalid memory result")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.observations.append(ReadObservation(path, self._tenant_id, self._at, inputs, (), error))
            raise ToolExecutionError(error) from exc
        excluded = tuple(m.memory_id for m in result
                         if self._max_age_seconds is not None
                         and self._at - m.recorded_at >= self._max_age_seconds)
        observation = ReadObservation(path, self._tenant_id, self._at, inputs, result,
                                      excluded_by_retention=excluded)
        # Audit raw adapter returns, then expose only policy-retained records.
        self.observations.append(observation)
        return observation.visible_memories

    def search(self, subject: str, key: str) -> tuple[Memory, ...]:
        return self._read("search", {"subject": subject, "key": key})

    def get(self, memory_id: str) -> Memory | None:
        result = self._read("get", {"memory_id": memory_id})
        return result[0] if result else None


def select(memories: tuple[Memory, ...], policy: str) -> Answer:
    if policy not in POLICIES:
        raise ValueError(f"unsupported policy: {policy}")
    if not memories:
        return Answer("unknown", None)
    if policy in ("last-write", "short-window"):
        chosen = max(memories, key=lambda m: (m.recorded_at, m.memory_id))
    elif policy == "valid-time":
        chosen = max(memories, key=lambda m: (m.effective_at, m.memory_id))
    else:
        effective_at = max(m.effective_at for m in memories)
        latest = tuple(m for m in memories if m.effective_at == effective_at)
        if len({m.value for m in latest}) > 1:
            return Answer("conflict", None, tuple(sorted(m.memory_id for m in latest)))
        chosen = max(latest, key=lambda m: (m.recorded_at, m.memory_id))
    return Answer("answer", chosen.value, (chosen.memory_id,))


def answer(query: Query, tools: TenantMemoryTools, policy: str) -> Answer:
    """At most search + one citation lookup. No fixture/expected-result argument."""
    try:
        candidates = tools.search(query.subject, query.key)
        selected = select(candidates, policy)
        if selected.status != "answer":
            return selected
        memory = tools.get(selected.evidence_ids[0])
        chosen = next(m for m in candidates if m.memory_id == selected.evidence_ids[0])
        if memory != chosen:
            return Answer("error", None, error="search/get evidence mismatch")
        return selected
    except ToolExecutionError as exc:
        return Answer("error", None, error=str(exc))
