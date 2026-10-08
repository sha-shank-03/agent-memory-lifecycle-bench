# Local execution evidence

The current bounded final delivery is **M2**, recorded in the final section below. The M1 section preserves its historical execution evidence; main subsequently accepted M1 independently and explicitly assigned M2. Worker checks do not substitute for main's pending whole-repository M2 review.

## Historical M1 execution

Execution date: **2026-10-07**. Environment: local Windows/PowerShell. Every shell workdir was `C:/Users/shash/Documents/CodexPortfolios/agentic-ai-2026-10-07/agent-memory-lifecycle-bench`. This report describes actual **offline mock** execution and local tests; no live-model evaluation occurred.

At this historical stage, main accepted PLAN.md and assigned only M1, recorded in `coordination/reviews/agent-memory-lifecycle-bench-M1.md`. The slice had four fictional scenarios, two policies, virtual time, SQLite/search/get/delete, tenant-bound reads, a bounded mock agent, private exact scoring, CLI/JSON evidence, README/license/attribution, and semantic tests. M2 comparison/full-suite/fault-demo/CI work had not yet been assigned or implemented.

## Commands actually run and observed results

| Command | Observed result |
| --- | --- |
| `py -3.11 --version` | Exit 0; Python 3.11.9. |
| `py -3.11 -m memory_lifecycle_bench validate examples/smoke-v1.json` | Exit 0; `VALID suite=smoke-v1 scenarios=4 categories=deletion,expiration,retention,tenant schema=1.0`. |
| `py -3.11 -m memory_lifecycle_bench run examples/smoke-v1.json --policy conservative --out work/smoke --strict` | Exit 0; 27/27 checks, 9/9 tasks, 7/7 positive answers, 2/2 required abstentions; zero contract violations. |
| `py -3.11 -m memory_lifecycle_bench run examples/smoke-v1.json --policy last-write --out work/last-write --strict` | Exit 0; same smoke-fixture counts. This does not imply equivalent behavior on stale/conflicting information. |
| `py -3.11 -m unittest discover -s tests -v` | Final source: exit 0, **29 tests passed**, runner reported 3.183 seconds. Test-run duration is not a memory performance benchmark. |
| `py -3.11 -c` report/failure inspection (expression below) | Exit 0; fingerprint/runtime/41 trace rows verified; all four negative adapters yielded failed reports, with the counts shown below. |
| `rg --files --hidden -g '!.git/**' -g '!work/**' -g '!**/__pycache__/**'` | Enumerated the package, fixture, tests, README/license/attribution and existing plan/instructions. |
| `git diff --check` | Exit 0, no output. New files were untracked in this initially empty repository, so this command was not a full whitespace validation of them. |

The initial store/policy slice passed 12 tests; adding fixture/runner/CLI/negative controls passed 28. A review found that returned known records also needed to match the requested subject/key or ID at the contract layer. That check and its semantic test were added; the final 29-test run and both final smoke commands above passed. No failing acceptance expectation was weakened or generated from the policy implementation.

Final conservative output, excluding only the platform-specific report path separator:

```text
OFFLINE MOCK | smoke-v1 | policy=conservative
scenarios=4 checks=27/27
tasks=9/9 positive_answers=7/7 required_abstentions=2/2
contract_violations=0
search: reads=18 deleted=0 expired=0 tenant=0
get: reads=16 deleted=0 expired=0 tenant=0
deletion: tasks=2/2 probes=6/6
expiration: tasks=2/2 probes=6/6
retention: tasks=2/2 probes=2/2
tenant: tasks=3/3 probes=4/4
```

The generated files are `work/smoke/report.json`, `work/smoke/trace.jsonl`, `work/last-write/report.json`, and `work/last-write/trace.jsonl`. They are local ignored execution artifacts and can be regenerated with the documented commands. Each report records Python **3.11.9** and SQLite **3.45.1**. The smoke file SHA-256 is:

```text
da593cef5f4a54a5afe899caa694fd4e9001f9dfe35fb7d2ec9e619e20c476cc
```

There are 41 trace rows: 5 puts, 2 deletes, and 34 reads. The 34 reads include 18 search and 16 get operations. Tests verify that report trace references resolve, repeated canonical results/trace ordering agree, and positive controls succeed before expiration/deletion absence checks. Expiration checks cover both reads at second 9, exactly at second 10, and after at second 11.

## Negative controls actually exercised

These deliberately defective adapters exist **only in tests** and use the same fictional smoke data. They are not production adapter modes or implemented M2 CLI fault demos.

| Test adapter | Failed report? | Observed result |
| --- | --- | --- |
| `EmptyStore` | Yes | Zero contract violations but **0/7 positive answers**. Safety by absence cannot earn task usefulness. |
| `ExpiredGetStore` | Yes | **2 expired get returns**, zero expired search returns. |
| `DeletedGetStore` | Yes | **3 deleted get returns** from its deliberately stale cache, zero deleted search returns. |
| `ForeignSearchStore` | Yes | **2 tenant leaks through search**, zero through get; positive answers 5/7. |

Additional passing tests verify backend errors do not earn abstention credit, incorrect read parameters are rejected even for a known record, future-effective records remain hidden, deletion survives reopen, identical replay cannot clear a tombstone, one tenant's deletion does not affect the other's shared ID, and quoted values are treated as bound SQL data. Malformed/oversized/version-mismatched/duplicate-key/invalid-clock inputs fail validation. CLI tests exercised strict failure exit 1 and invalid input exit 2 through the actual `main` entry function; these are unit-level CLI invocations rather than separate terminal launches.

The report/failure inspection was run as this exact Python command:

```powershell
py -3.11 -c "import json; from pathlib import Path; from memory_lifecycle_bench.runner import evaluate; from memory_lifecycle_bench.suite import load_suite; from tests.test_suite_runner_cli import EmptyStore,ExpiredGetStore,DeletedGetStore,ForeignSearchStore; r=json.loads(Path('work/smoke/report.json').read_text(encoding='utf-8')); print('suite_sha256=' + r['suite_sha256']); print('runtime=' + json.dumps(r['runtime'],sort_keys=True)); print('trace_rows=' + str(len(Path('work/smoke/trace.jsonl').read_text(encoding='utf-8').splitlines()))); s=load_suite('examples/smoke-v1.json'); factories=(EmptyStore,ExpiredGetStore,DeletedGetStore,ForeignSearchStore); rows=[(f.__name__,evaluate(s,'conservative',f)[0]) for f in factories]; print(json.dumps([{'adapter':name,'passed':v['passed'],'positive_answers':v['summary']['positive_answers'],'contract_violations':v['summary']['contract_violations'],'search_violations':v['supported_paths']['search']['violations'],'get_violations':v['supported_paths']['get']['violations']} for name,v in rows],sort_keys=True))"
```

## Historical M1 unexecuted and bounded claims

- Main's independent acceptance is pending; worker test results do not replace it.
- M2 is unassigned: no four-policy comparison command, full 16-scenario suite, user-facing fault-demo commands, external adapter example, or CI workflow exists yet.
- No Linux/hosted CI execution, external/vendor/backend integration, public benchmark, authenticated production tenancy, distributed concurrency, or scalability/performance test was executed.
- No physical erasure, backups/log/context deletion, security certification, legal compliance, or live-model behavior is claimed. Earlier fictional content remains in input and evidence traces; the assertions concern supported retrieval paths.
- No pip installs, runtime downloads, machine-wide setup, paid calls, external account changes, publication, or pushes occurred. These lightweight stdlib tests required no heavy-build resource lease.

Primary-source research, licenses, pinned contracts/runtime and planned action versions remain in PLAN.md and THIRD_PARTY.md. M1 stopped at **milestone_review**. Main's subsequent independent acceptance and bounded M2 assignment are recorded below.

## Final M2 execution and handoff

Execution date: **2026-10-07**, local Windows/PowerShell, CPython **3.11.9** via `py -3.11`, SQLite **3.45.1**. All shell commands used the assigned checkout root stated above. No third-party runtime, test or build dependencies were installed. This is deterministic **offline mock** execution, with newly authored fictional records and independently authored expected outcomes.

Authorization: `coordination/reviews/agent-memory-lifecycle-bench-M2.md` records main's independent M1 acceptance: 29 tests and fresh validation/two-policy smoke runs, each 27/27 checks, 9/9 tasks, 7/7 positive answers, 2/2 abstentions and zero supported-path violations. It explicitly assigned this final M2 and required stopping for whole-repository review, with no automatic M3.

Implemented M2 includes four documented configurations, 16 scenarios across six categories, two actual close/reopen events, raw adapter return auditing before retention, utility/abstention/lifecycle metrics, trusted Python adapter API/example, three fixed fictional CLI defects, complete architecture/contract/report documentation, recorded examples and pinned free CI. CLI adapter imports and caller-provided fault suites are absent by design.

### Commands actually executed

| Command | Exit / observed result |
| --- | --- |
| `py -3.11 -m unittest discover -s tests -v` | Final source: **0; 40 tests passed**, runner reported 25.852 seconds. This is test duration, not a performance benchmark. |
| `py -3.11 scripts/verify_demo.py --out work/m2-verification` | **0**; `DEMO CHECKS PASSED`, `benchmark_comparison_passed=false`, expected faulty CLI exits 1. Seven actual child processes and their exit/stdout/stderr receipts were checked, together with report contents and unchanged fixture bytes. |
| `py -3.11 work/export_recorded_examples.py` | **0**; copied the final reference report/trace byte-for-byte and derived the labeled comparison excerpt without recomputing any outcomes. |
| `py -3.11 work/audit_m2_artifacts.py` | **0**; recorded bytes equal execution bytes, comparison excerpt measurements equal canonical measurements, all **24 local Markdown links** resolve, 153 trace rows/references inspect correctly and prepared CI settings are present. Static inspection only; no hosted CI execution. |

`work/m2-verification/summary.json` contains the exact subprocess argument arrays, observed/expected exit codes, fixture digest and `verification_passed=true`. `command-0.stdout.txt` through `command-6.stdout.txt` and corresponding stderr files preserve each child receipt. Those ignored work artifacts can be regenerated; durable recorded examples are under `examples/reports/`.

For every child, the actual executable was:

~~~text
C:\Users\shash\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe
~~~

The following table shows the exact remaining arguments. `{root}` expands to `C:\Users\shash\Documents\CodexPortfolios\agentic-ai-2026-10-07\agent-memory-lifecycle-bench\work\m2-verification` in each recorded array; it is a documentation abbreviation, not shell syntax.

| Receipt | Child arguments | Observed exit |
| --- | --- | --- |
| 0 | `-m memory_lifecycle_bench validate examples/lifecycle-v1.json` | 0 |
| 1 | `-m memory_lifecycle_bench run examples/lifecycle-v1.json --policy conservative --out {root}\reference --strict` | 0 |
| 2 | `-m memory_lifecycle_bench compare examples/lifecycle-v1.json --out {root}\comparison` | 0; analysis completed, aggregate benchmark failed as expected |
| 3 | `-m examples.adapter_demo --out {root}\adapter` | 0 |
| 4 | `-m memory_lifecycle_bench fault-demo --fault expired-get --out {root}\expired-get` | 1 |
| 5 | `-m memory_lifecycle_bench fault-demo --fault deleted-search --out {root}\deleted-search` | 1 |
| 6 | `-m memory_lifecycle_bench fault-demo --fault tenant-search --out {root}\tenant-search` | 1 |

The initial expanded 40-test run exited **1** because the new pairing test found that a copied tenant case relied on a successful task's reads rather than an explicit earlier matching positive probe for its later absence probe. Two positive search/get probes were added to the **full fixture only**; the pairing assertion was preserved and strengthened coverage was retained. The original accepted smoke fixture was not changed. Final tests and the final seven-process CLI verification above then passed. Initial 85-check full-suite artifacts predate these additional probes and are not the recorded final examples.

### Final observed results

Full fixture: **16 scenarios, 125 events**, categories retention 2, expiration 3, deletion 3, tenant 2, stale 3, conflict 3. File size 53,345 bytes. SHA-256:

~~~text
eb7af32157386fe1e8687c61c77432316c3d06b876b7a943b6b2d58574169e2f
~~~

The original smoke digest remains `da593cef5f4a54a5afe899caa694fd4e9001f9dfe35fb7d2ec9e619e20c476cc`. The verifier checks both source files remain byte-for-byte unchanged across all child executions.

The conservative reference and trusted adapter example each passed **87/87 checks**, **36/36 tasks**, **28/28 positive answers**, **8/8 required abstentions**, and **51/51 probes**, with **zero contract violations**. Reference supported-path reads: **61 search, 54 get**. Trace: **153 rows** comprising 30 puts, 6 deletes, 115 reads and 2 reopens. Reopens actually close and reconstruct the store at the same database path; expiry/deletion negatives and retained positive controls then verify persistence. Adapter-factory tests observe 18 instances for 16 scenarios plus 2 reopens, opaque ordinal filenames, closure and temporary-directory cleanup.

| Configuration | Checks | Tasks | Positive answers | Required abstentions | Stale answers | Confident conflict errors | Retention task losses | Report passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| last-write | 84/87 | 33/36 | 27/28 | 6/8 | 1 | 2 | 0 | false |
| short-window | 78/87 | 31/36 | 25/28 | 6/8 | 1 | 2 | 2 | false |
| valid-time | 85/87 | 34/36 | 28/28 | 6/8 | 0 | 2 | 0 | false |
| conservative | 87/87 | 36/36 | 28/28 | 8/8 | 0 | 0 | 0 | true |

All four had zero supported-path contract violations. The aggregate comparison has `completed=true` and **`passed=false`**. Default comparison exit 0 indicates completed analysis; strict aggregate gating is separately tested to exit 1. These authored scenarios illustrate differences between the explicit policies and cannot establish general superiority.

| Fixed fictional fault | Named violations | Clean reference | Positive controls preserved | Input bytes unchanged | Fault report / CLI |
| --- | --- | --- | --- | --- | --- |
| expired-get | 2 expired returns through get | passed | 3/3 | true | passed=false / exit 1 |
| deleted-search | 2 deleted returns through search | passed | 3/3 | true | passed=false / exit 1 |
| tenant-search | 2 foreign-tenant returns through search | passed | 4/4 | true | passed=false / exit 1 |

Each diagnostic independently parsed its fixed fictional bytes for clean and defective execution; saved input, clean report and faulty report digests agree. Each has `diagnostic_valid=true` only because the clean result, positive controls, unchanged bytes and intended violations were verified. That diagnostic status never changes the failed benchmark status. A negative diagnostic test deliberately breaks a positive control and confirms `diagnostic_valid=false`.

Meaningful M2 checks cover the exact seven-day boundary on **both** paths, late historical records, ID tie handling, conflicting/agreeing claims, conflict resolution, actual reopen, raw expired-return detection despite retention filtering, independent positive/negative controls, adapter oracle-field isolation, preserved failed comparisons, all fault CLI exits and rejection of production-input fault switches. Existing M1 tests continue to cover supported search/get expiry/deletion/tenancy, empty-store utility failure, backend error abstention failure, deterministic traces, malformed inputs, tombstone/replay and SQL-bound values.

### Documentation, CI and unexecuted checks

`README.md`, `docs/architecture.md`, `docs/suite-v1.md`, `docs/adapter-v1.md`, `docs/report-v1.md` and `docs/limitations.md` describe actual implemented contracts, trust boundary, schemas, contribution and limits. `examples/reports/reference/report.json` and `trace.jsonl` are unchanged final execution copies. `comparison-summary.json` is explicitly labeled as an excerpt with unavailable child report references removed; its measurements and failed aggregate remain unchanged.

CI is **prepared locally**, using checkout v7.0.1 at `3d3c42e5aac5ba805825da76410c181273ba90b1` and setup-python v7.0.0 at `5fda3b95a4ea91299a34e894583c3862153e4b97`, previously verified against primary releases/manifests and `git ls-remote`. The Windows/Ubuntu matrix pins Python 3.11.9, has `contents: read`, `persist-credentials: false`, no dependency install and no paid calls, and invokes unit tests plus the CLI verifier. **No hosted CI or Linux execution occurred.**

- Main's independent whole-repository M2 acceptance remains pending; M1 was independently accepted.
- External memory/vendor/backend integration, live models, authentication, distributed concurrency, load/performance/cost and public benchmark comparisons remain unexecuted or out of scope.
- Supported-path exclusion does not claim physical erasure, removal from backups/logs/context, security certification or legal compliance. Earlier fictional content remains in input and evidence.
- The trusted adapter runs synchronously in-process without sandbox or timeout; no arbitrary adapter code is loaded by CLI. Multi-file output publication is not atomic.
- No pip installs, runtime downloads, heavy builds, paid calls, external account changes, publication, commits or pushes occurred. Small stdlib checks required no heavy resource lease. The repository's new files remain untracked; historical `git diff --check` was not validation of those additions.

M2 stops at **milestone_review** for main's independent acceptance. No M3, resource-heavy integration or external publication is authorized by this delivery.
