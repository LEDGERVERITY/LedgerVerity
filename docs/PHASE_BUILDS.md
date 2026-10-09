# Private Engineering Roadmap (Not for root README)

Internal development phases and status are **not** claims of program approval.

| Phase | Goal | State | Gate |
|---|---|---|---|
| 01 | Input-only JSONL consistency checker, fixture tests | IMPLEMENTED — REQUIRES INDEPENDENT RECHECK | Local unittest evidence and source inspection |
| 02 | Official ETL export mapping and validated JSON schema | NOT STARTED | Reproduce official fields and shape; negative cases |
| 03 | Independent Stellar ledger-XDR event reference | NOT STARTED | Verified original evidence, canonical event identity |
| 04 | Token transfer normalization (SEP-41, muxed, exceptions) | NOT STARTED | Rules anchored to versioned SEP and empirical fixtures |
| 05 | Differential reconciliation against ETL output | NOT STARTED | Detect missing, extra, duplicated and misinterpreted records |
| 06 | Scalable bounded CLI, SARIF/JSON, external review | NOT STARTED | Reproducible integration tests and useful verified findings |
| 07 | Release readiness, public documentation and optional branding | NOT STARTED | Clean install, signed-off evidence, authorized publish |

Proposed tests for later phases: event-order changes, identical legitimate events, malformed XDR, misleading duplicate similarities, mixed networks, failed transactions, muxed addresses, duplicate diagnostic emissions, nonconforming SEP-41/57 formats, provider coverage gaps, partial ledger ranges, archive retention. Tests are **not executed** merely because listed.
