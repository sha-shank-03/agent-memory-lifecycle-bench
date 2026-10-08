"""Trusted Python adapter entry point. Factories receive a database path, not oracles."""

from pathlib import Path
from typing import Callable

from .model import Store
from .runner import evaluate, write_reports
from .store import SQLiteStore
from .suite import load_suite


def run_file(suite_path: str | Path, out_dir: str | Path, policy: str = "conservative",
             store_factory: Callable[[Path], Store] = SQLiteStore) -> dict:
    suite = load_suite(suite_path)
    report, traces = evaluate(suite, policy, store_factory)
    write_reports(out_dir, report, traces)
    return report
