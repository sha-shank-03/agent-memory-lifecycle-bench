"""Trusted adapter wiring using only the public Store 1.0 operations."""

import argparse
from pathlib import Path

from memory_lifecycle_bench.api import run_file
from memory_lifecycle_bench.model import Memory
from memory_lifecycle_bench.runner import terminal_summary
from memory_lifecycle_bench.store import SQLiteStore


class SupportedReadAdapter:
    """Replace delegation with your trusted local implementation; no oracle argument."""

    def __init__(self, database_path: Path) -> None:
        self._store = SQLiteStore(database_path)

    def put(self, memory: Memory) -> bool:
        return self._store.put(memory)

    def delete(self, tenant_id: str, memory_id: str) -> bool:
        return self._store.delete(tenant_id, memory_id)

    def search(self, tenant_id: str, subject: str, key: str, at: int) -> tuple[Memory, ...]:
        return self._store.search(tenant_id, subject, key, at)

    def get(self, tenant_id: str, memory_id: str, at: int) -> Memory | None:
        return self._store.get(tenant_id, memory_id, at)

    def close(self) -> None:
        self._store.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Trusted local Store 1.0 adapter demonstration")
    parser.add_argument("--out", type=Path, default=Path("work/adapter-demo"))
    args = parser.parse_args()
    suite_path = Path(__file__).with_name("lifecycle-v1.json")
    report = run_file(suite_path, args.out, store_factory=SupportedReadAdapter)
    print(terminal_summary(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
