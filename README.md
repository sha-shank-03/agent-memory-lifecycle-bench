# Agent Memory Lifecycle Bench

[![CI](https://github.com/sha-shank-03/agent-memory-lifecycle-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/sha-shank-03/agent-memory-lifecycle-bench/actions/workflows/ci.yml)

Open-source MIT project. [Project context](docs/PROJECT_CONTEXT.md) · [Independent local verification](docs/INDEPENDENT_VERIFICATION.md) · [Contributing](CONTRIBUTING.md)

Evaluate retained recall, expiration, deletion, tenant separation, stale facts, and conflicts before changing an assistant's memory layer. Sixteen fictional scenarios compare four simple policies and link failed checks to retrieval evidence. Positive usefulness and required abstention have separate denominators: an empty store cannot pass by returning no forbidden records.

Execution is **offline mock**: a bounded deterministic agent queries structured facts in SQLite. No LLM, extraction, embeddings, provider, external memory service, API key, or package install is involved. All included data is newly authored fiction. Recorded examples are local mock evidence, not replayed or fresh model results.

## Quickstart

From the checkout root with the existing CPython 3.11.9 baseline:

~~~powershell
py -3.11 --version
py -3.11 -m memory_lifecycle_bench validate examples/lifecycle-v1.json
py -3.11 -m memory_lifecycle_bench run examples/lifecycle-v1.json --policy conservative --out work/reference --strict
py -3.11 -m memory_lifecycle_bench compare examples/lifecycle-v1.json --out work/comparison
py -3.11 -m unittest discover -s tests -v
~~~

The reference run passed **87/87 checks**, **36/36 tasks**, **28/28 positive answers**, and **8/8 required abstentions** with zero lifecycle violations. It performs 61 search and 54 get reads and two actual close/reopen events. These are authored-fixture results, not general superiority or public benchmark scores. [EVIDENCE.md](EVIDENCE.md) records actual commands, exit codes, development failures, and unexecuted checks.

| Configuration | Retention | Selection | Observed tasks | Observed result |
| --- | --- | --- | --- | --- |
| last-write | Unbounded | Latest recorded time, then greatest ID | 33/36 | One stale answer, two confident conflict errors |
| short-window | Seven days | Same last-write selection | 31/36 | Two additional retention losses |
| valid-time | Unbounded | Latest effective time, then greatest ID | 34/36 | Two confident conflict errors |
| conservative | Unbounded | Latest effective time; incompatible ties abstain | 36/36 | Passes this explicit fixture |

All four have zero deletion/expiry/tenant violations. Comparison prints **overall_passed=false** because failed baselines remain failed. Default comparison exit 0 means analysis completed, not that configurations passed. Add `compare --strict` to enforce aggregate pass; use `run --strict` to gate the policy you select.

On this machine `py -3.11` is Python 3.11.9/SQLite 3.45.1; plain `python` resolves differently. `.python-version` records the baseline without changing PATH. On another OS use its Python 3.11 interpreter; Linux/hosted CI execution remains unexecuted. Reports record actual runtime versions because bundled SQLite can differ.

## Reproduce the failures

Each fixed fictional diagnostic first runs a clean reference, then injects one adapter defect. Each **exits 1** because memory behavior fails:

~~~powershell
py -3.11 -m memory_lifecycle_bench fault-demo --fault expired-get --out work/fault-expiry
py -3.11 -m memory_lifecycle_bench fault-demo --fault deleted-search --out work/fault-delete
py -3.11 -m memory_lifecycle_bench fault-demo --fault tenant-search --out work/fault-tenant
~~~

The observed faults each produced two named violations: expired get, deleted search, and foreign-tenant search. A diagnostic is valid only if the clean run and positive controls pass, identical input bytes/digests remain unchanged, and the intended violation appears. Its failed benchmark stays `passed=false`; `diagnostic_valid=true` describes exposing the defect. There is no input-suite option for fault-demo and no fault toggle on run/compare.

To reproduce and assert the entire CLI flow:

~~~powershell
py -3.11 scripts/verify_demo.py --out work/demo-verification
~~~

It saves exact subprocess command/exit/stdout/stderr receipts and a summary. `verification_passed=true` means demo assertions passed; `benchmark_comparison_passed=false` preserves the baseline failures. This is also the prepared CI entry after unit tests, with no paid calls/dependency install.

## Useful examples and reports

The [full fixture](examples/lifecycle-v1.json) has retention 2, expiration 3, deletion 3, tenant 2, stale 3, and conflict 3 scenarios. It covers the seven-day boundary, exact expiry, replay, warmed deletion, persistence through reopen, tenant-shared IDs/foreign deletion, delayed history, future-effective updates, conflicting/agreeing ties, and conflict resolution. Every deletion/expiry absence probe has an earlier successful matching probe. Permanent positive controls after reopen distinguish persistence from starting empty. The [original smoke](examples/smoke-v1.json) remains byte-for-byte unchanged.

Reports separate task/probe utility, abstention, stale/conflict errors, retention loss, and both-path violations. Every check links to a read trace ID. Raw adapter returns are audited before retention filtering; traces distinguish raw records, age exclusions, and delivered IDs. Retention cannot hide a broken adapter's lifecycle leak.

`--out` overwrites report.json/trace.jsonl in that directory. Comparison creates policy subdirectories and comparison.json; fault demos add input.json and a clean reference/ report. Choose different directories to retain runs. Temporary databases are closed/removed. Earlier fictional content remains in inputs/evidence: supported-path exclusion is not physical erasure.

[Recorded example reports](examples/reports/README.md) are actual local artifacts and an explicitly labeled summary excerpt. Opening them is not a new execution; regenerate fresh evidence with the commands above.

## Trusted Python adapter

~~~powershell
py -3.11 -m examples.adapter_demo --out work/adapter-demo
~~~

The [example adapter](examples/adapter_demo.py) delegates only through public Store operations. Use `memory_lifecycle_bench.api.run_file(..., store_factory=YourAdapter)` for your trusted local code. A factory receives a database path; reads receive tenant, query key/ID, and virtual time. No oracles, descriptions, category/task IDs, or suite objects are adapter inputs. Reopen calls close and invokes the factory again at the same path. CLI has no dynamic-import adapter option.

| Specification | Version / link |
| --- | --- |
| Architecture | [Components and evaluator boundary](docs/architecture.md) |
| Suite schema | 1.0: [Complete event/field semantics](docs/suite-v1.md) |
| Adapter schema | 1.0: [Signatures, trust and persistence](docs/adapter-v1.md) |
| Reports/traces/comparison | 1.0: [Fields and pass/completion semantics](docs/report-v1.md) |
| Contribution/limits | [Overlap and unmeasured behavior](docs/limitations.md) |

Times are integer simulated seconds, with tied events in fixture order and no sleep. Both mandatory paths require matching tenant, no tombstone, effective_at <= t, and no expiry or **t < expires_at**. Short-window additionally excludes age **>= 604800** from both tool paths without changing storage/expiry. Deletion tombstones one tenant/ID identity; replay cannot restore it and a new legitimate record needs a new ID. Missing/foreign IDs have the same not-found result.

Inputs reject unknown fields, unsupported versions, duplicate JSON/record/check IDs, malformed types, backwards time and bounds violations. Limits: 1 MiB, 100 scenarios, 500 events/scenario, and 64 versions of a tenant/subject/key.

| Exit | Meaning |
| --- | --- |
| 0 | Validation succeeds or analysis completes without an enforced failure gate |
| 1 | Retrieval/backend failure; any strict task/probe failure; fixed fault diagnostic |
| 2 | Invalid/missing input or invalid CLI arguments |

Non-strict utility mismatches remain failed reports despite completion exit 0. Passing a synthetic fixture does not certify privacy/security, production authentication, erasure, reasoning, vendor compatibility, scale or cost. Trusted Python adapters are synchronous and in-process, not sandboxed or timed out.

## License and CI

Original code/fixtures are [MIT](LICENSE). There are zero third-party pip runtime/test/build dependencies. [THIRD_PARTY.md](THIRD_PARTY.md) records runtime licenses, research attribution and verified immutable action pins. [CI](.github/workflows/ci.yml) is prepared for Windows/Ubuntu, Python 3.11.9, read-only permissions and no persisted checkout credentials; hosted execution/publication remain unexecuted. [PLAN.md](PLAN.md) is the accepted historical design. Bounded final M2 awaits main's independent whole-repository review.

## Get the source

```sh
git clone https://github.com/sha-shank-03/agent-memory-lifecycle-bench.git
cd agent-memory-lifecycle-bench
```

Follow the quickstart above for runtime/dependency setup. Demos use fictional/mock data; initial dependency setup, where required, is separate from offline execution.
