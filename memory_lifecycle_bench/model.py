"""Public task/store values. Oracles are defined separately in suite.py."""

from dataclasses import dataclass
from typing import Protocol
import re

CONTRACT_VERSION = "1.0"
ID_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")


class ValidationError(ValueError):
    """Input does not satisfy the supported, bounded fixture contract."""


def identifier(value: object, where: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValidationError(f"{where}: expected a lowercase identifier (1..64 characters)")
    return value


def seconds(value: object, where: str) -> int:
    if type(value) is not int or not 0 <= value <= 2**53 - 1:
        raise ValidationError(f"{where}: expected nonnegative integer simulated seconds")
    return value


def text_value(value: object, where: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{where}: expected nonblank text of at most {maximum} characters")
    return value


@dataclass(frozen=True)
class Memory:
    tenant_id: str
    memory_id: str
    subject: str
    key: str
    value: str
    recorded_at: int
    effective_at: int
    expires_at: int | None
    source: str

    def validate(self) -> None:
        for name in ("tenant_id", "memory_id", "subject", "key"):
            identifier(getattr(self, name), name)
        text_value(self.value, "value")
        text_value(self.source, "source")
        seconds(self.recorded_at, "recorded_at")
        seconds(self.effective_at, "effective_at")
        if self.expires_at is not None:
            seconds(self.expires_at, "expires_at")
            if self.expires_at <= self.effective_at:
                raise ValidationError("expires_at: must be greater than effective_at")


@dataclass(frozen=True)
class Query:
    subject: str
    key: str
    description: str


@dataclass(frozen=True)
class Answer:
    status: str
    value: str | None
    evidence_ids: tuple[str, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class ReadObservation:
    path: str
    tenant_id: str
    at: int
    inputs: dict[str, str]
    memories: tuple[Memory, ...]
    error: str | None = None
    excluded_by_retention: tuple[str, ...] = ()

    @property
    def visible_memories(self) -> tuple[Memory, ...]:
        return tuple(m for m in self.memories if m.memory_id not in self.excluded_by_retention)


class Store(Protocol):
    """Trusted in-process Store 1.0. All reads are tenant-scoped and time-filtered."""

    def put(self, memory: Memory) -> bool: ...
    def delete(self, tenant_id: str, memory_id: str) -> bool: ...
    def search(self, tenant_id: str, subject: str, key: str, at: int) -> tuple[Memory, ...]: ...
    def get(self, tenant_id: str, memory_id: str, at: int) -> Memory | None: ...
    def close(self) -> None: ...


class VirtualClock:
    def __init__(self) -> None:
        self.now = 0

    def advance(self, at: int) -> None:
        seconds(at, "at")
        if at < self.now:
            raise ValidationError("at: virtual clock cannot move backwards")
        self.now = at
