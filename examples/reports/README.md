# Recorded offline examples

These files were produced by actual local **offline mock** execution on 2026-10-07, using CPython 3.11.9 / SQLite 3.45.1 on Windows. Opening them does not execute the agent or evaluate a live model. All content is fictional. They illustrate the evidence format and this authored suite's outcomes.

- [Reference report](reference/report.json) and [read/event trace](reference/trace.jsonl) are unchanged copies from the final conservative CLI run: 87/87 checks, 36/36 tasks, 28/28 positive answers, 8/8 required abstentions, zero lifecycle violations and two actual reopens.
- [Comparison summary excerpt](comparison-summary.json) copies the actual four-policy comparison measurements. It is explicitly an excerpt, with child report-file references removed because the full child output tree is not included here. It preserves `completed=true` and **`passed=false`**. Use a fresh comparison for canonical child reports/traces.

The input digest is `eb7af32157386fe1e8687c61c77432316c3d06b876b7a943b6b2d58574169e2f`, matching [lifecycle-v1.json](../lifecycle-v1.json). The deterministic reports omit wall-clock timestamps and temporary database paths; runtime versions and the adapter name remain visible. [Report schema](../../docs/report-v1.md) explains trace links, raw/delivered records, utility versus abstention, and completion versus pass.

From the checkout root, reproduce fresh artifacts with:

~~~powershell
py -3.11 -m memory_lifecycle_bench run examples/lifecycle-v1.json --policy conservative --out work/reference --strict
py -3.11 -m memory_lifecycle_bench compare examples/lifecycle-v1.json --out work/comparison
py -3.11 scripts/verify_demo.py --out work/demo-verification
~~~

The last command separately asserts the CLI flow and expected failing fault exits. Its `verification_passed=true` does not change the comparison's failed benchmark result. [Execution evidence](../../EVIDENCE.md) records observed commands, results, development failures, and unexecuted checks. Hosted CI, Linux and vendor/live-model evaluation remain unexecuted.
