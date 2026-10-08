# Dependencies and research attribution

Source/license retrieval date: **2026-10-07**. Original project code and fictional fixtures are under the repository's MIT license. No external benchmark code or data is vendored.

The checkout CLI and tests use only the Python standard library. The reproducibility baseline is CPython 3.11.9, verified locally through `py -3.11`, with bundled SQLite 3.45.1. Runtime binaries are not redistributed. CPython's [pinned license file](https://raw.githubusercontent.com/python/cpython/v3.11.9/LICENSE) includes the PSF license agreement and historical notices; [SQLite's notice](https://www.sqlite.org/copyright.html) identifies its deliverable code/documentation as public domain. Actual Python and SQLite versions appear in every run report.

Research references influenced scope rather than becoming dependencies:

| Reference | License file inspected | Relationship |
| --- | --- | --- |
| [LongMemEval](https://github.com/xiaowu0162/LongMemEval) | [MIT](https://raw.githubusercontent.com/xiaowu0162/LongMemEval/main/LICENSE) | Existing update/temporal/abstention benchmark; no code/data copied. |
| [LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2) | [Apache-2.0](https://raw.githubusercontent.com/xiaowu0162/LongMemEval-V2/main/LICENSE) | Existing agent-memory harness; general separation of retrieval input from gold metadata, independently implemented here. |
| [LoCoMo](https://github.com/snap-research/locomo) | [CC BY-NC 4.0](https://raw.githubusercontent.com/snap-research/locomo/main/LICENSE.txt) | Existing conversational-memory evaluation; no dataset or code redistribution. |
| [LangMem](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/) | [MIT](https://raw.githubusercontent.com/langchain-ai/langmem/main/LICENSE) | Namespaces and configurable memory consolidation/removal concepts; not installed. |
| [Mem0](https://docs.mem0.ai/platform/features/memory-expiration) | [OSS Apache-2.0](https://raw.githubusercontent.com/mem0ai/mem0/main/LICENSE) | Documented lifecycle path semantics; no vendor/service integration or compatibility claim. |

Repository licenses above are not treated as blanket licenses for separately hosted datasets or service APIs.

Prepared M2 CI-only references (not vendored): actions/checkout v7.0.1 at `3d3c42e5aac5ba805825da76410c181273ba90b1` ([MIT](https://raw.githubusercontent.com/actions/checkout/v7.0.1/LICENSE)); actions/setup-python v7.0.0 at `5fda3b95a4ea91299a34e894583c3862153e4b97` ([MIT](https://raw.githubusercontent.com/actions/setup-python/v7.0.0/LICENSE)). Official manifests/releases were read and tags independently resolved with git ls-remote during planning; evidence is in PLAN.md. Their Node 24 runtime belongs to the hosted runner. CI pins Python 3.11.9, read-only permissions and no persisted checkout credentials. Hosted execution/publication remain unexecuted.
