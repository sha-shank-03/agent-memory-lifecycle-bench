# Agent Memory Lifecycle Bench: proposed implementation plan

Planning date and source retrieval date: **2026-10-07**. Historical accepted design: main explicitly assigned M1, independently accepted it, and assigned bounded final M2 on 2026-10-07. Current actual implementation evidence is in EVIDENCE.md; proposed assertions below do not substitute for results. Repository: `C:/Users/shash/Documents/CodexPortfolios/agentic-ai-2026-10-07/agent-memory-lifecycle-bench`.

## 1. User problem and concrete journey

An agent developer changes a memory policy or backend and needs to know whether it still remembers useful facts, stops retrieving expired/deleted records, respects tenant boundaries, and handles outdated or conflicting facts. A single QA accuracy score obscures these tradeoffs. This tool will execute small, fictional, time-controlled lifecycle scenarios and produce separate utility and retrieval-contract results with the failing query and returned memory IDs.

The initial customer is a developer maintaining a support or internal-assistant memory layer. From a checkout, they validate a JSON suite, compare four policies, inspect a terminal summary plus JSON evidence, and add their own fictional scenario. A Python adapter protocol allows them to run the same harness against a trusted local memory implementation. No vendor integration, account, server, model, or package installation is necessary for the reference demo.

Proposed Windows journey, from the repository root:

```powershell
py -3.11 -m memory_lifecycle_bench validate examples/lifecycle-v1.json
py -3.11 -m memory_lifecycle_bench compare examples/lifecycle-v1.json --out work/demo
py -3.11 -m memory_lifecycle_bench run examples/lifecycle-v1.json --policy conservative --out work/reference --strict
```

`compare` completes even when a simple baseline has task failures, because seeing those failures is the purpose of comparison; it exits nonzero for retrieval-contract violations or malformed input. `run --strict` exits 1 for any failed task or contract check. Exit 2 means invalid input/configuration. Backend execution errors are explicit failed checks, never converted silently to unknown answers. Final command names and this exit contract will be documented together.

## 2. Existing tools, overlap, and contribution

Primary sources were opened and read, not inferred from search snippets:

| Existing work | Verified overlap | How this repository is scoped |
| --- | --- | --- |
| [LongMemEval](https://github.com/xiaowu0162/LongMemEval/blob/main/README.md) | QA benchmark covering updates, temporal reasoning, and abstention; public data and evaluation scripts. | A small lifecycle regression suite with explicit deletion, expiration, tenant and ID-lookup probes; no leaderboard comparison. |
| [LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2) | Current official agent-memory harness for trajectory-derived experience and downstream QA. Its backend interface keeps gold question metadata private during retrieval. | Adopt the general evaluator/adapter separation principle, implemented independently for structured lifecycle events. No V2 code, trajectories, models, or dataset will be copied. |
| [LoCoMo](https://github.com/snap-research/locomo) | Long conversational histories with QA/evidence annotations. | New fictional fixtures are needed for controlled lifecycle events. No LoCoMo data will be redistributed. |
| [LangMem concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/) and [semantic-memory guide](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/) | Memory consolidation, namespaces, and configurable removal/storage behavior. | Test explicit behavior at a supported adapter boundary rather than introduce an extraction framework. |
| [Mem0 expiration](https://docs.mem0.ai/platform/features/memory-expiration) and [deletion](https://docs.mem0.ai/core-concepts/memory-operations/delete) | Lifecycle operations already exist. The documented expiration contract filters search/list but still allows fetching expired records by ID. | Make path coverage and semantics visible: this reference profile requires both `search` and `get` to exclude expired/deleted records. This is our profile, not a claim that a different vendor contract is defective. |

The original contribution is the combination of a compact event-based fixture format, explicit supported-read-path contract checks, controlled policy comparisons, and useful task outcomes in one offline developer regression tool. This is an engineering contribution, not a claim to have invented memory evaluation or a universally better memory algorithm.

## 3. Narrow MVP and non-goals

The MVP consists of one package/CLI, one SQLite reference adapter, four built-in policy configurations, a deterministic mock task agent, a bounded JSON suite, exact oracles, terminal/JSON reports, failure demonstrations, tests, and docs/CI.

The proposed complete suite contains **16 scenarios** across six categories: retention (2), expiration (3), deletion (3), tenant separation (2), stale information (3), and conflicts (3). Scenario assertions may contain several probes; reports count probes and denominators, not just scenarios.

All names, organizations, preferences, service routes, and values are newly authored fictional data. Example tasks ask which queue a fictional support case should use or which contact preference is current. Natural-language descriptions make the demo readable; structured subject/key queries and exact answers keep scoring deterministic.

Non-goals: live LLM execution or LLM judges; natural-language extraction; embeddings/vector databases; public benchmark scores; external Mem0/LangMem integrations; MCP/A2A/HTTP servers; authenticated multi-tenant production hosting; distributed concurrency; graph memory; dashboards; physical media erasure; removal from backups/logs or an agent's earlier context; legal-compliance claims. Recorded traces are evidence of the offline run; no fresh model execution is implied and replay is not a separate MVP feature.

## 4. Architecture and explicit semantics

```text
Validated fictional JSON suite
          |
Virtual clock + scenario runner ---- private exact expectations
          |                                  |
Tenant-bound memory tools -> Store v1         |
          |              SQLite reference    |
          v                                  v
Bounded deterministic mock agent -> independent scorer -> reports
          |
Policy configuration + retrieved evidence only
```

Use **Python**, because fixtures, adapters, evaluation, and report generation are the core work. Java would add a build/dependency requirement without a benefit for this bounded CLI. Use only `argparse`, `dataclasses`, `json`, `hashlib`, `pathlib`, `sqlite3`, `tempfile`, `typing`, and `unittest` plus ordinary standard-library support. No service or pip dependency is justified.

The local fixture, adapter, and report contracts each start at **1.0**. These are project-defined formats, not existing public protocols. Reject unsupported versions rather than guess compatibility. A documented `typing.Protocol` exposes `put`, tenant-scoped `delete`, `search`, and `get`; the Python harness takes an adapter factory. CLI supports the reference store only initially, avoiding arbitrary dynamic imports. Custom Python adapters are trusted code and run in-process; the harness is not a sandbox.

Memory records have `(tenant_id, memory_id)` identity, `subject`, `key`, a scalar string `value`, `recorded_at`, `effective_at`, optional `expires_at`, and a fictional source label. Store these as separate columns with bound SQL parameters and a composite primary key. Each scenario starts with a fresh database. A reopen event tests persisted deletion/expiration behavior without implementing a general service.

Time is nonnegative integer **simulated seconds since scenario T=0**, never wall-clock sleep. Events are ordered; tied event times retain fixture order. Reject backward clock movement, unknown fields/operations, malformed IDs/types, duplicate probe IDs, invalid time bounds, and nonidentical reuse of an existing record ID. Identical record replay is idempotent, but must not resurrect a tombstoned ID. A new legitimate memory needs a new ID. Bound input to 1 MiB, 100 scenarios, 500 events per scenario, and 64 memory versions per subject/key; exceeding a limit is a validation error, not truncated success.

Reference supported retrieval semantics:

- Every operation requires a nonempty explicit tenant; tenant selection is bound by the harness/tool session rather than supplied by the mock agent. This demonstrates logical isolation, not authentication.
- At time `t`, a record is visible only if tenant matches, it is not tombstoned, `effective_at <= t`, and `expires_at is null or t < expires_at`. Expiration is exclusive: the record is unavailable exactly at its expiry time.
- `search(subject, key)` and `get(memory_id)` both apply those rules. There is no raw/admin read tool, wildcard tenant, cache, or top-k truncation in the supported agent path.
- `delete(tenant, id)` atomically tombstones that exact record. Missing/foreign IDs return the same not-found result. Repeated deletion is harmless. It does not delete every memory with the same value or physically wipe SQLite pages. Tests use unique target values to make absence assertions precise.
- A policy retention horizon also applies consistently to both supported read paths. An unbounded configuration retains records until an explicit lifecycle event; the short window excludes records when `t - recorded_at >= 604800` (seven simulated days). Reports distinguish horizon losses from explicit expiry.

Compare these deliberately simple configurations on the same events and expectations:

| Policy | Retention | Answer selection |
| --- | --- | --- |
| `last-write` | Unbounded | Latest observed/recorded record; ID is the documented deterministic tie-break. |
| `short-window` | Seven days | Same last-write rule, providing a clean retention ablation. |
| `valid-time` | Unbounded | Greatest effective time; ID breaks equal-time ties. |
| `conservative` | Unbounded | Greatest effective time; incompatible values tied at that time yield `conflict` abstention; matching duplicate claims agree. |

All policies share the mandatory retrieval-contract profile. Policies differ in usefulness, not tenant/deletion/expiry enforcement. No policy is claimed to reconstruct real-world truth: the suite explicitly supplies authoritative effective times. A late-arriving historical fact exposes last-write staleness; incompatible same-time facts expose the cost of a deterministic tie-break; a newer unambiguous fact resolves a conflict. Future-effective facts are not yet usable.

The mock agent has a fresh task context per query and a maximum of two read-tool calls: search, then optional get for its chosen citation. It never receives gold answers, lifecycle labels, the whole fixture, or a database handle. It emits a structured answer/unknown/conflict result and memory-ID citations. The scorer owns expectations and compares status, exact value, evidence IDs, and supported-path probes independently. The input/expectation separation is a code-level contract, not isolation from someone editing repository files.

Report per-category task pass counts/denominators, positive-answer recall, required abstention accuracy, stale-answer count, incorrect confident answers on conflicts, and separate violations for deleted, expired, or foreign-tenant records returned by each read path. An always-empty test adapter must fail positive utility assertions. Never rank a policy solely on safety or one aggregate percentage. Include suite SHA-256, policies/versions, execution kind `offline_mock`, Python/SQLite versions, virtual event/query times, actual returned IDs, expected-vs-observed checks, and trace links. Omit wall-clock latency benchmarks from the MVP; deterministic operation counts may be reported as counts only.

## 5. Pinned dependencies, artifact availability, and attribution

All sources below were retrieved/read on **2026-10-07**. No archives, models, datasets, runtimes, or packages were downloaded or installed during planning.

| Component | Pin / availability evidence | License / treatment |
| --- | --- | --- |
| Reference interpreter | **CPython 3.11.9** is installed and verified with `py -3.11`; [official release and Windows artifacts](https://www.python.org/downloads/release/python-3119/). This is the reproducibility baseline, not a claim to be the current patch release. | [Pinned CPython license](https://raw.githubusercontent.com/python/cpython/v3.11.9/LICENSE): PSF license agreement plus included historical notices. Runtime not redistributed. |
| SQLite | Bundled with that interpreter, observed **3.45.1**; use no extension or separately installed SQLite package. [Standard-library API](https://docs.python.org/3.11/library/sqlite3.html). Record the actual bundled SQLite version on every run; CI distribution builds can differ. | [SQLite public-domain notice](https://www.sqlite.org/copyright.html). No vendored binaries. |
| Unit testing/type protocol | CPython standard library; [unittest](https://docs.python.org/3.11/library/unittest.html), [typing](https://docs.python.org/3.11/library/typing.html#typing.Protocol). | Covered by the CPython notices. Zero third-party runtime/test/build dependencies for the checkout workflow. |
| CI checkout | **actions/checkout v7.0.1**, full SHA **3d3c42e5aac5ba805825da76410c181273ba90b1**. [Release/commit](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1); tag independently resolved by `git ls-remote`. [Manifest](https://raw.githubusercontent.com/actions/checkout/v7.0.1/action.yml) uses the runner's Node 24. | [MIT](https://raw.githubusercontent.com/actions/checkout/v7.0.1/LICENSE); CI-only dependency, referenced rather than copied. |
| CI Python setup | **actions/setup-python v7.0.0**, full SHA **5fda3b95a4ea91299a34e894583c3862153e4b97**. [Release/commit](https://github.com/actions/setup-python/commit/5fda3b95a4ea91299a34e894583c3862153e4b97); tag independently resolved. [Manifest](https://raw.githubusercontent.com/actions/setup-python/v7.0.0/action.yml) uses Node 24. | [MIT](https://raw.githubusercontent.com/actions/setup-python/v7.0.0/LICENSE); CI-only. Exact `python-version: 3.11.9`, no dependency cache/install. Hosted CI execution remains unexecuted locally. |
| Local contracts | Suite **1.0**, store adapter **1.0**, report **1.0**, SQLite schema **1**, mock agent **1.0**. | Original project code/fixtures planned under **MIT**, with a `THIRD_PARTY.md` distinguishing dependencies from research references. No packaging backend is needed for `python -m` from a checkout. |

Research-reference artifacts and licenses were also checked: [LongMemEval code MIT](https://raw.githubusercontent.com/xiaowu0162/LongMemEval/main/LICENSE); [LongMemEval-V2 code Apache-2.0](https://raw.githubusercontent.com/xiaowu0162/LongMemEval-V2/main/LICENSE); [LoCoMo repository CC BY-NC 4.0](https://raw.githubusercontent.com/snap-research/locomo/main/LICENSE.txt); [LangMem MIT](https://raw.githubusercontent.com/langchain-ai/langmem/main/LICENSE); [Mem0 OSS Apache-2.0](https://raw.githubusercontent.com/mem0ai/mem0/main/LICENSE). Their official repositories expose code/docs and the benchmark repositories link public data locations. None is a selected dependency, and repository licenses are not treated as blanket permission for separately hosted datasets or service APIs. The MVP needs none of these external artifacts.

Default `python` on this machine actually resolves to **3.12.7**, SQLite **3.45.3**. `py -3.11` resolves to the brief's **3.11.9**, SQLite **3.45.1**. Document the launcher distinction rather than change PATH or install a runtime. A lightweight smoke test under the existing default interpreter can be recorded after implementation, but support claims depend on tests actually run.

## 6. Bounded milestones and planned acceptance

These commands and assertions are **proposed, not observed results**. Each implementation boundary requires a further accepted assignment from main.

### M1: first runnable end-to-end slice

Implement a checkout-runnable package, strict fixture validation, virtual clock, SQLite store/get/search/delete, tenant-bound tools, mock agent, `last-write` and `conservative` policies, independent exact scoring, and terminal/JSON reports. Start with a four-scenario `examples/smoke-v1.json`: retention of one useful fact, exact expiry boundary, deletion after a successful read, and two tenants sharing a record ID. Include a short offline README and the MIT license immediately. No extra backends, network calls, packaging install, or broad performance work.

```powershell
py -3.11 -m memory_lifecycle_bench validate examples/smoke-v1.json
py -3.11 -m memory_lifecycle_bench run examples/smoke-v1.json --policy conservative --out work/smoke --strict
py -3.11 -m unittest discover -s tests -v
```

Acceptance: validation exits 0 with four scenarios; strict run exits 0; report identifies `offline_mock`, conservative policy, nonzero positive-answer denominator, and zero deleted/expired/tenant violations for both reads. The before-delete/before-expiry checks must return the target before the negative checks can pass. Unit tests prove exact-boundary behavior, tenant-scoped IDs, and explicit not-found outcomes. Save commands/output in `EVIDENCE.md`; stop at `milestone_review` for main's independent check and next assignment.

### M2: policy comparison, meaningful failures, and completion docs/CI

Add `short-window`, `valid-time`, the full 16-scenario suite, close/reopen checks, out-of-order information/conflict cases, stable comparison reports, the trusted Python adapter API example, and a self-contained diagnostic `fault-demo`. Faults are deliberately broken local adapters over hardcoded fictional data, not modes for production input. Add docs for suite/adapter/report schemas, architecture, limitations/original contribution, licensing/attribution, quickstart/demo, and evidence. Prepare a GitHub Actions workflow for `windows-latest` and `ubuntu-latest`, exact Python/action pins, read-only repository permissions, `persist-credentials: false`, and no paid calls; do not publish or claim a hosted run occurred.

```powershell
py -3.11 -m memory_lifecycle_bench validate examples/lifecycle-v1.json
py -3.11 -m memory_lifecycle_bench compare examples/lifecycle-v1.json --out work/comparison
py -3.11 -m memory_lifecycle_bench run examples/lifecycle-v1.json --policy conservative --out work/reference --strict
py -3.11 -m memory_lifecycle_bench fault-demo --fault expired-get --out work/fault-expiry
py -3.11 -m memory_lifecycle_bench fault-demo --fault deleted-search --out work/fault-delete
py -3.11 -m memory_lifecycle_bench fault-demo --fault tenant-search --out work/fault-tenant
py -3.11 -m unittest discover -s tests -v
```

Acceptance assertions:

- Full suite validates 16 scenarios and all six categories; every category has a positive or necessary paired control, avoiding vacuous success.
- Comparison exits 0 when lifecycle contracts hold, includes all four configurations and per-category numerators/denominators, and shows concrete expected baseline failures: `short-window` loses the old permanent fact, `last-write` answers the late historical value, and `valid-time` confidently chooses an incompatible tied claim.
- `conservative --strict` exits 0 on the authored reference suite. This is a fixture-specific result, not an overall superiority claim.
- Each fault demo exits 1 and creates a report naming its specific read path and injected violation. Tests confirm that the scorer detects those defects; merely running a faulty adapter is not a passing outcome.
- Repeated identical runs have identical canonical results and trace ordering. Runtime metadata is explicit; no elapsed-time performance claim or fabricated baseline score appears.
- Documentation commands actually run on this Windows machine; local tests and unexecuted hosted CI are distinguished in the evidence report.

Meaningful required tests include paired positive/negative search AND get probes before/at/after expiry; warmed-read then delete and reopen; deleted ID replay cannot resurrect; identical IDs across tenants; deletion in one tenant leaves the other intact; absent/empty tenant fails validation; quoted fictional values use bound SQL correctly; late old/new information ordering; future-effective records; same-time different/same values and conflict resolution; always-empty adapter loses useful recall; backend exception is not scored as a correct abstention; malformed/oversized/version-mismatched input; nonzero CLI failure exits; and scorer/agent inputs contain no private oracle fields. Use hand-authored expected outcomes, not expectations generated by the policy implementation.

## 7. Risks, resolved choices, and open decisions

- **Synthetic scope:** exact structured facts isolate lifecycle semantics; they do not measure an LLM's extraction, reasoning, or resistance to prompt injection. Label reports and README accordingly.
- **Deletion scope:** supported reads exclude tombstoned IDs. Fixture files, SQLite pages, evidence from earlier reads, and outside caches can still contain fictional content. No erasure or privacy guarantee is implied.
- **Contract mismatch:** a future vendor adapter must document its actual expiry and deletion semantics and the mapped benchmark profile. The explicit exclusive-second reference profile must not be silently called a universal standard.
- **Policy/oracle circularity:** independent fixtures specify task truth; utilities do not read oracle metadata. Negative adapters and positive controls verify the harness can detect failures. Main performs independent acceptance; workers do not rewrite acceptance to force passes.
- **Adapter trust:** custom adapters are trusted Python code. Any real account, authenticated tenant principal, asynchronous consistency, retry, timeout, or network adapter requires separately accepted scope.
- **Bounded storage:** version-count limits are fixture bounds, not scalability guarantees. No heavy build, integration suite, or large download is planned; ask main for a named resource lease before any such work becomes necessary.
- **Environment/CI:** use the verified `py -3.11` baseline. CI actions/artifact pins are verified, but hosted runners and Linux behavior remain unexecuted checks until actually available.

Routine decisions resolved: Python/stdlib, SQLite reference store, virtual seconds, exact scoring, MIT, in-process trusted adapter API, no external datasets, four simple configurations, and strict read-path contract. **No essential human question blocks planning or M1.** The only next authorization needed is main's accepted-plan assignment of M1; no implementation may start from this document alone.

## 8. Actual planning evidence

Commands already run (all shell workdirs were the assigned absolute repository path):

| Command / read | Observed result |
| --- | --- |
| `Get-Content` assigned `AGENTS.md`, own `status.json`, own `assignment.txt`, and `coordination/user-request.txt` | Planning-only boundary, exclusive edit ownership, resource lease rule, and human authorization for worker coordination confirmed. |
| `rg --files --hidden -g '!.git/**'` | Only `AGENTS.md` before plan creation. |
| `git status --short` | `?? AGENTS.md` before plan creation. |
| `git log -1 --oneline` | No commits on `main`; reported a fatal no-commit message, an expected empty-repository state. |
| `python --version` and `python -c` runtime inspection | CPython 3.12.7, SQLite 3.45.3; default interpreter differs from brief. |
| `py -0p` and `py -3.11 -c` runtime inspection | Python launcher has 3.11; explicit runtime is 3.11.9 with SQLite 3.45.1. |
| `git ls-remote --tags https://github.com/actions/checkout.git refs/tags/v7.0.1` | Resolved `3d3c42e5aac5ba805825da76410c181273ba90b1`. |
| `git ls-remote --tags https://github.com/actions/setup-python.git refs/tags/v7.0.0` | Resolved `5fda3b95a4ea91299a34e894583c3862153e4b97`. |
| Primary-source web page/license/manifest reads linked above | Pages and selected action tags available; runtime licenses and context-reference licenses checked. One incorrect LangMem URL returned an error; corrected official guide was then read successfully. |

Unexecuted: implementation, all acceptance commands, unit tests, benchmark metrics, hosted CI, custom/vendor adapters, production/authentication tests, physical deletion tests, paid or live-model execution. No test pass or benchmark number is asserted by this planning report.
