"""Checkout entry point: python -m memory_lifecycle_bench."""

import argparse
from pathlib import Path
import sqlite3
import sys

from .agent import POLICIES
from .model import ValidationError
from .runner import compare, evaluate, terminal_summary, write_reports
from .faults import FAULTS, run_fault_demo
from .suite import load_suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fictional offline/mock agent memory lifecycle evaluation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a bounded Suite 1.0 JSON file")
    validate.add_argument("suite", type=Path)
    run = subparsers.add_parser("run", help="run a deterministic mock agent against SQLite")
    run.add_argument("suite", type=Path)
    run.add_argument("--policy", choices=POLICIES, default="conservative")
    run.add_argument("--out", type=Path, required=True, help="directory for report.json and trace.jsonl")
    run.add_argument("--strict", action="store_true", help="exit 1 for any failed task or probe")
    compare_parser = subparsers.add_parser("compare", help="compare four configurations; completion is not a pass")
    compare_parser.add_argument("suite", type=Path)
    compare_parser.add_argument("--out", type=Path, required=True)
    compare_parser.add_argument("--strict", action="store_true", help="exit 1 if any configuration fails")
    fault_parser = subparsers.add_parser("fault-demo", help="fixed fictional fault only; no input suite option")
    fault_parser.add_argument("--fault", choices=FAULTS, required=True)
    fault_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "fault-demo":
        try:
            report = run_fault_demo(args.fault, args.out)
        except (OSError, sqlite3.Error, ValidationError) as exc:
            print(f"EXECUTION FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(f"OFFLINE MOCK FAULT DEMO | {args.fault} | result=FAILED")
        print(terminal_summary(report))
        diagnostic = report["fault_demo"]
        print(f"diagnostic_valid={str(diagnostic['diagnostic_valid']).lower()} "
              f"positive_controls_preserved={str(diagnostic['positive_controls_preserved']).lower()} "
              f"input_bytes_unchanged={str(diagnostic['input_bytes_unchanged']).lower()}")
        print(f"report={args.out / 'report.json'}")
        return 1  # Named faulty behavior is a failed benchmark, including a valid demonstration.
    try:
        suite = load_suite(args.suite)
    except (ValidationError, OSError) as exc:
        print(f"INVALID INPUT: {exc}", file=sys.stderr)
        return 2
    if args.command == "validate":
        categories = ",".join(sorted({s.category for s in suite.scenarios}))
        print(f"VALID suite={suite.suite_id} scenarios={len(suite.scenarios)} categories={categories} schema=1.0")
        return 0
    if args.command == "compare":
        try:
            comparison = compare(suite, args.out)
        except (OSError, sqlite3.Error, ValidationError) as exc:
            print(f"EXECUTION FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(f"OFFLINE MOCK COMPARISON COMPLETED | {suite.suite_id} "
              f"| overall_passed={str(comparison['passed']).lower()}")
        for row in comparison["configurations"]:
            summary = row["summary"]
            print(f"{row['policy']}: passed={str(row['passed']).lower()} "
                  f"tasks={summary['tasks']['passed']}/{summary['tasks']['total']} "
                  f"positive_answers={summary['positive_answers']['passed']}/{summary['positive_answers']['total']} "
                  f"abstentions={summary['required_abstentions']['passed']}/{summary['required_abstentions']['total']} "
                  f"contract_violations={summary['contract_violations']}")
        print(f"comparison={args.out / 'comparison.json'}")
        contract_failure = any(r["summary"]["contract_violations"] for r in comparison["configurations"])
        return 1 if contract_failure or (args.strict and not comparison["passed"]) else 0
    try:
        report, traces = evaluate(suite, args.policy)
        write_reports(args.out, report, traces)
    except (OSError, sqlite3.Error, ValidationError) as exc:
        print(f"EXECUTION FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(terminal_summary(report))
    print(f"report={args.out / 'report.json'} trace={args.out / 'trace.jsonl'}")
    if report["summary"]["contract_violations"] or (args.strict and not report["passed"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
