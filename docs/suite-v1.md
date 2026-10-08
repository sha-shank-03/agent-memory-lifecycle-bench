# Suite 1.0 schema

UTF-8 JSON, optionally with a BOM. Unknown/duplicate keys, NaN/Infinity, unsupported versions and semantic bounds violations are errors. This is the complete field/semantic schema; suite.py validates it without a schema-library dependency. Version 1.0 describes the completed prepublication MVP including reopen; tool version is 0.2.0.

Identifiers match `[a-z][a-z0-9_.-]{0,63}`. Times are integers in 0..2^53-1 (no booleans/floats). Text is nonblank, at most 512 characters, unnormalized.

| Object | Required fields / constraints |
| --- | --- |
| Root | schema_version string 1.0; suite_id identifier; fictional boolean true; scenarios array of 1..100 scenarios |
| Scenario | id identifier unique per suite; category retention/expiration/deletion/tenant/stale/conflict; events array of 1..500 ordered events, including a query/probe |

Input limit: 1 MiB. At most 64 distinct versions per tenant/subject/key; identical replay adds none. Query/probe IDs share one uniqueness scope per scenario. Stores are independent across scenarios.

## Events

All except reopen require op, at, tenant (identifier). Events must be nondecreasing in at, with ties in array order. Exact additional fields:

| op | Fields |
| --- | --- |
| put | memory object |
| delete | memory_id identifier |
| query | id identifier, task object, expected object |
| probe | id identifier, path search/get, inputs object, expected_ids unique identifier array of 0..64, reason present/expired/deleted/tenant/future/absent |
| reopen | Only op and at; no tenant or extras. Close entire scenario adapter and construct it again at the same path. |

Memory object requires all these fields (expiry null is explicit):

| Field | Type / constraint |
| --- | --- |
| id, subject, key | Identifiers; tenant/id is identity |
| value, source | Nonblank bounded strings; source is fictional provenance |
| recorded_at | Simulated time no later than the put event |
| effective_at | Simulated time; may precede/follow recorded time |
| expires_at | Null or time strictly greater than effective_at; may already have passed when put arrives |

Reusing identity with any changed field/timestamp/source is invalid. Identical replay preserves expiry/tombstone; new legitimate observations need new IDs. Deleting one ID does not remove all historical versions or other records with the same value.

Task requires subject/key identifiers and description text. Expected requires status answer/unknown/conflict, value, evidence_ids. Answer needs a nonblank value and exactly one evidence ID; unknown has null value/no evidence; conflict has null value and at least two IDs. IDs are unique/sorted internally. Expectations are evaluator-only assertions; validation verifies shape, not authored real-world truth.

Probe inputs have exactly subject/key for search or memory_id for get. Expected IDs are sorted internally; reason is a private label and never changes retrieval behavior. Included expiry/deletion absence probes have matching earlier positive probes. Backend errors fail even when expected IDs are empty.

At time t, both mandatory paths require matching tenant, no tombstone, effective_at <= t, and no expiry or t < expires_at. Foreign/missing IDs share not-found. Short-window additionally excludes age >= 604800 on both tool paths while raw returns stay audited. Example: [full suite](../examples/lifecycle-v1.json); [unchanged smoke](../examples/smoke-v1.json).
