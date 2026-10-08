# Report, trace and comparison 1.0 schemas

Stable UTF-8 JSON/JSONL. Outputs are recorded offline mock evidence, not new model execution. Completed tool release is 0.2.0; contract schemas remain 1.0. Readers tolerate additive output fields; input remains strict. Counts are integers, not timing/cost estimates.

## Run report

| Root fields | Type / meaning |
| --- | --- |
| schema_version, suite_schema_version, store_contract_version | Strings 1.0 |
| sqlite_schema_version | Integer 1, reference storage |
| tool_version, mock_agent_version, policy_version | Explicit version strings |
| execution_kind | offline_mock; fault_demo marks injection explicitly |
| suite_id, suite_sha256 | Identifier and SHA-256 of exact bytes |
| policy | last-write/short-window/valid-time/conservative |
| retention, retention_seconds | unbounded/null or seven-days/604800 |
| adapter | Factory name, trusted-adapter fallback; no certification |
| scenario_count | Integer, distinct from check denominators |
| runtime | Object with python/sqlite version strings |
| summary | Counters below |
| categories | Category -> task/probe -> {passed,total} |
| supported_paths | search/get -> {reads, violations: {kind: count}} |
| passed | All exact utility/probe checks and mandatory contracts passed |
| checks | Ordered check array below |
| trace_file | Relative trace.jsonl |
| fault_demo | Optional fixed diagnostic object below |

Summary fields: passed/total for all checks; tasks/positive_answers/required_abstentions each {passed,total}; contract_violations; stale_answers; confident_conflict_errors; retention_task_losses; reopens. A task pass needs exact status/value/citations and no execution/contract error. Gold-answer tasks are positive; gold unknown/conflict tasks require abstention. Backend errors earn neither.

Stale answers count stale-category answer-status results with wrong value. Confident conflict errors count answer-status when conflict is required. Retention losses count gold-answer tasks becoming unknown with observed age exclusions. They are fixture-specific outcomes, not general truth, extraction, cost or reasoning.

Violation kinds: deleted, expired, tenant, future, unexpected_record, corrupt_payload, backend_error. Counts are violation instances; one record can violate multiple predicates. Aggregate sums both paths/kinds, not distinct leaking records/reads. Horizon loss is utility, not a mandatory violation.

## Checks and traces

Every check has scenario/category/event_index/at/id/type/tenant_id/passed/failures (string array), trace_refs, contract_violations (kind/detail or kind/memory_id), retention_excluded_ids (read occurrences, not deduplicated).

- Task: task {subject,key,description}; expected {status,value,evidence_ids}; observed {status,value,evidence_ids,error}. Observed may have error status; error is null/string. Gold is private during execution, intentionally visible afterward.
- Probe: path/reason/expected_ids/observed_ids. Observed IDs reflect delivered records after age filtering; contract inspection still sees raw records.

Check IDs are scenario-scoped; evidence IDs are tenant-scoped. Shared IDs do not imply shared content.

Every trace row has scenario/category/event_index/at/type. Put adds memory/inserted; delete adds tenant_id/memory_id/changed; reopen adds closed/reopened booleans, emitted after actual close/construction succeed. Read adds trace_id (scenario.e<index>.r<index>), path/tenant_id/inputs, memories (raw full records), error, excluded_by_retention, delivered_memory_ids, contract_violations. Earlier fictional content remains in traces; deletion does not erase evidence.

## Comparison

Root fields: schema_version/execution_kind/suite_id/suite_sha256/completed/passed/configurations. Each configuration has policy/passed/summary/categories/supported_paths/retention_seconds/report_file (relative child report). Child report/trace are complete.

Completed means all evaluations/artifacts finished. Passed requires every child pass. Intentional baseline failures stay false. Default compare exit 0 means completed without mandatory violations; --strict also enforces aggregate pass. Printed output and CI receipts distinguish these states.

## Fixed faults and verification receipts

Fault metadata fields: fault/expected_path/expected_violation/violation_count, positive_controls_preserved/positive_control_count, input_bytes_unchanged/reference_passed/input_file/reference_report/diagnostic_valid. Copied input.json digest matches independent clean/fault parses. Valid diagnostic needs a clean pass, positive controls, unchanged bytes and a named violation. It never overrides benchmark pass; CLI always exits 1.

Recorded comparison-summary.json is explicitly an excerpt, not a canonical complete comparison. The verifier writes a distinct offline_demo_verification receipt with verification_passed, benchmark_comparison_passed, command/expected_exit/exit_code/stdout/stderr-file entries, input digest and reference summary. Assertions passing does not make failed baseline behavior pass.
