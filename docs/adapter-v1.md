# Trusted Store 1.0 schema and contract

Call `memory_lifecycle_bench.api.run_file(suite_path, out_dir, policy="conservative", store_factory=YourAdapter)`. It returns a report after writing evidence. The factory receives a temporary pathlib.Path once per fresh scenario and again at each reopen; persist in that path. Filenames use ordinals, not semantic scenario labels. [Runnable adapter](../examples/adapter_demo.py).

Memory is frozen with tenant_id, memory_id, subject, key, value, recorded_at, effective_at, expires_at, source; field bounds are in [Suite 1.0](suite-v1.md). No expected answer/category/query ID is included.

| Signature | Result / behavior |
| --- | --- |
| put(memory: Memory) | bool: true new insertion; false identical replay; reject changed identity; replay cannot clear tombstone |
| delete(tenant_id: str, memory_id: str) | bool: true newly tombstoned identity; false missing/foreign/already deleted; no wildcard |
| search(tenant_id: str, subject: str, key: str, at: int) | tuple[Memory, ...]: matching active records, mandatory tenant/deletion/effective/expiry predicates; reference uses deterministic ID order, no top-k |
| get(tenant_id: str, memory_id: str, at: int) | Memory or None: exact active identity under same predicates; None absent/foreign/deleted/expired/future |
| close() | None: release handles; persist state for a factory invocation at the same path |

Reads accept no descriptions, oracles, fixture objects, category/task IDs or admin switch. Virtual time is explicit. Returned fields must match submitted records and requested scope; known records for a different subject/key/ID are defects.

Reference puts/deletes commit individual SQLite transactions; schema user_version is 1 and incompatible versions fail. This is not distributed transactionality or exactly-once external effects. Tombstones remain on disk, with no physical erasure claim.

Seven-day retention is a separate tool filter; raw results stay audited. Implement mandatory predicates in a custom adapter, not policy/oracle-tailored answers. Read exceptions/wrong container/object types become explicit backend errors, not unknown. Construction/write/close/reopen/output errors can abort; Python callers receive exceptions and the reference CLI exits nonzero for its supported local I/O/SQLite failures. Interrupted outputs can be partial.

Adapters are trusted synchronous Python without sandbox/authentication/time/side-effect/resource enforcement. Input/read-count bounds are not such enforcement. CLI has no dynamic-import adapter option, and no external vendor integration/compatibility is claimed.
