"""Reproduce the offline CLI flow and assert results without trusting exit 0 alone."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    # Acceptance gates remain active when Python runs with optimization enabled.
    if not condition:
        raise ValueError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify fictional offline CLI examples and expected failures")
    parser.add_argument("--out", type=Path, default=ROOT / "work/demo-verification")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    inputs = {name: (ROOT / "examples" / name).read_bytes() for name in ("smoke-v1.json", "lifecycle-v1.json")}
    receipts = []

    def execute(arguments, expected_exit):
        command = [sys.executable, *arguments]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        index = len(receipts)
        (out / f"command-{index}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (out / f"command-{index}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
        receipts.append({"command": command, "expected_exit": expected_exit, "exit_code": completed.returncode,
                         "stdout_file": f"command-{index}.stdout.txt", "stderr_file": f"command-{index}.stderr.txt"})
        require(completed.returncode == expected_exit,
                f"exit {completed.returncode}, expected {expected_exit}: {arguments}")

    def report(relative):
        return json.loads((out / relative).read_text(encoding="utf-8"))

    summary = {"kind": "offline_demo_verification", "verification_passed": False, "commands": receipts}
    try:
        execute(["-m", "memory_lifecycle_bench", "validate", "examples/lifecycle-v1.json"], 0)
        execute(["-m", "memory_lifecycle_bench", "run", "examples/lifecycle-v1.json", "--policy", "conservative",
                 "--out", str(out / "reference"), "--strict"], 0)
        execute(["-m", "memory_lifecycle_bench", "compare", "examples/lifecycle-v1.json",
                 "--out", str(out / "comparison")], 0)
        execute(["-m", "examples.adapter_demo", "--out", str(out / "adapter")], 0)
        reference = report("reference/report.json")
        require(reference["passed"] and reference["scenario_count"] == 16, "reference must pass all 16 scenarios")
        require(reference["summary"]["positive_answers"] == {"passed": 28, "total": 28}, "positive utility differs")
        require(reference["summary"]["required_abstentions"] == {"passed": 8, "total": 8}, "abstentions differ")
        require(reference["summary"]["reopens"] == 2, "two actual reopens are required")
        require(reference["summary"]["contract_violations"] == 0, "reference retrieval violation")
        require(report("adapter/report.json")["passed"], "trusted adapter example failed")
        comparison = report("comparison/comparison.json")
        require(comparison["completed"] and not comparison["passed"], "comparison must preserve baseline failures")
        rows = {r["policy"]: r for r in comparison["configurations"]}
        require(set(rows) == {"last-write", "short-window", "valid-time", "conservative"}, "configuration set differs")
        require(rows["conservative"]["passed"], "conservative reference failed")
        require(all(not rows[p]["passed"] for p in ("last-write", "short-window", "valid-time")), "expected utility failures disappeared")
        require(all(r["summary"]["contract_violations"] == 0 for r in rows.values()), "baseline lifecycle violation")
        require(rows["last-write"]["summary"]["stale_answers"] == 1, "last-write stale failure disappeared")
        require(rows["short-window"]["summary"]["retention_task_losses"] == 2, "short-window losses differ")
        require(rows["valid-time"]["summary"]["confident_conflict_errors"] == 2, "valid-time conflicts differ")
        for fault, path, kind in (("expired-get", "get", "expired"), ("deleted-search", "search", "deleted"),
                                  ("tenant-search", "search", "tenant")):
            execute(["-m", "memory_lifecycle_bench", "fault-demo", "--fault", fault,
                     "--out", str(out / fault)], 1)
            failed = report(f"{fault}/report.json")
            clean = report(f"{fault}/reference/report.json")
            require(not failed["passed"] and clean["passed"], f"{fault}: incorrect pass state")
            require(failed["fault_demo"]["diagnostic_valid"], f"{fault}: invalid diagnostic")
            require(failed["fault_demo"]["positive_controls_preserved"] and failed["fault_demo"]["input_bytes_unchanged"],
                    f"{fault}: positive control or immutable input changed")
            require(failed["supported_paths"][path]["violations"][kind] > 0, f"{fault}: named violation missing")
            require(sha256((out / fault / "input.json").read_bytes()).hexdigest() == failed["suite_sha256"] == clean["suite_sha256"],
                    f"{fault}: input fingerprint differs")
        require(all((ROOT / "examples" / name).read_bytes() == raw for name, raw in inputs.items()), "example input bytes changed")
        summary.update({"verification_passed": True, "benchmark_comparison_passed": comparison["passed"],
                        "reference_summary": reference["summary"], "input_bytes_unchanged": True,
                        "suite_sha256": reference["suite_sha256"]})
    except (AssertionError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not summary["verification_passed"]:
        print(f"DEMO VERIFICATION FAILED: {summary.get('error')}", file=sys.stderr)
        return 1
    print("DEMO CHECKS PASSED | benchmark_comparison_passed=false | expected faulty CLI exits=1")
    print(f"summary={out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
